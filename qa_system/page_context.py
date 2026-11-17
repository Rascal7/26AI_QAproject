"""Read the target page's structure for AI test design, and check generated selectors on the real page.

The browser runs in a separate process with the same restricted environment as test execution
(no API keys). Only element attributes and visible text are collected, never input values.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from urllib.parse import urljoin, urlsplit
from demo_web.db import ROOT
from qa_system.evidence import redact

MAX_ELEMENTS = 80
MAX_PAGES = 5  # other same-site pages read after the start page
MAX_OTHER_ELEMENTS = 40
TIMEOUT = 90
# Paths written in requirement text, e.g. "/home 으로 이동" -> /home. Not part of a URL or a fraction like 1/3.
PATH_IN_TEXT = re.compile(r'(?<![\w.:/])/[A-Za-z0-9_\-][A-Za-z0-9_\-./]*')
URL_IN_TEXT = re.compile(r'https?://[^\s"\'<>)\]]+')  # full addresses; other sites are filtered out later
# Never open links that may change state just by being visited.
RISKY_LINK = re.compile(r'log-?out|sign-?out|delete|remove|destroy|unsubscribe|deactivate|로그아웃|삭제|탈퇴', re.I)

# Collects interactive and landmark elements with the most stable selector that matches exactly one element.
EXTRACT_JS = r"""
() => {
  const q = v => String(v).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  const text = el => (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 80);
  const count = sel => { try { return document.querySelectorAll(sel).length; } catch { return 0; } };
  const visible = el => {
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const selectorFor = el => {
    const tag = el.tagName.toLowerCase(), found = [];
    const tid = el.getAttribute('data-testid');
    if (tid) found.push(`[data-testid="${q(tid)}"]`);
    if (el.id) found.push('#' + CSS.escape(el.id));
    const name = el.getAttribute('name');
    if (name) found.push(`${tag}[name="${q(name)}"]`);
    const aria = el.getAttribute('aria-label');
    if (aria) found.push(`${tag}[aria-label="${q(aria)}"]`);
    const href = tag === 'a' && el.getAttribute('href');
    if (href) found.push(`a[href="${q(href)}"]`);
    const type = el.getAttribute('type');
    if (type && ['input', 'button'].includes(tag)) found.push(`${tag}[type="${q(type)}"]`);
    const role = el.getAttribute('role');
    if (role) found.push(`[role="${q(role)}"]`);
    found.push(tag);
    for (const sel of found) if (count(sel) === 1) return [sel, true];
    const label = text(el);
    if (label && ['a', 'button', 'h1', 'h2', 'h3', 'label'].includes(tag))
      return [`${tag}:has-text("${q(label)}")`, true];
    return [found[0], false];
  };
  const query = 'h1,h2,h3,form,label,input:not([type=hidden]),textarea,select,button,a[href],' +
                '[role=button],[role=link],[role=alert],[role=status],[aria-live]';
  const described = new Set();
  for (const el of document.querySelectorAll('[aria-describedby]'))
    for (const id of el.getAttribute('aria-describedby').split(/\s+/)) if (id) described.add(id);
  const candidates = [...document.querySelectorAll(query)];
  for (const id of described) {
    const el = document.getElementById(id);
    if (el && !candidates.includes(el)) candidates.push(el);
  }
  const elements = [];
  for (const el of candidates) {
    if (elements.length >= MAX) break;
    const live = el.matches('[role=alert],[role=status],[aria-live]') || described.has(el.id);
    if (!visible(el) && !live) continue;  // keep empty message areas: they show errors later
    const [selector, unique] = selectorFor(el);
    const item = {tag: el.tagName.toLowerCase(), selector, unique, text: text(el)};
    for (const attr of ['type', 'name', 'placeholder', 'role', 'aria-label', 'autocomplete']) {
      const v = el.getAttribute(attr);
      if (v) item[attr] = v.slice(0, 80);
    }
    if (el.labels && el.labels.length) item.label = text(el.labels[0]);
    if (el.required) item.required = true;
    if (el.disabled) item.disabled = true;
    if (live && !visible(el)) item.initially_empty = true;
    if (el.tagName === 'A') item.href = el.getAttribute('href').slice(0, 200);
    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') delete item.text;  // never read typed values
    elements.push(item);
  }
  return {title: document.title, lang: document.documentElement.lang || '', elements};
}
""".replace('MAX', str(MAX_ELEMENTS))


class PageContextError(Exception):
    pass


def _origin(url):
    parts = urlsplit(url)
    return parts.scheme, parts.hostname, parts.port or (443 if parts.scheme == 'https' else 80)


def _open(playwright, url, channel):
    browser = playwright.chromium.launch(channel=channel or None)
    page = browser.new_page(viewport={'width': 1280, 'height': 900})
    page.set_default_timeout(10000)

    def restrict(route):
        # Stay on the registered site; assets from other hosts may still load.
        if route.request.is_navigation_request() and _origin(route.request.url) != _origin(url):
            route.abort()
        else:
            route.continue_()

    page.route('**/*', restrict)
    response = page.goto(url, wait_until='domcontentloaded', timeout=20000)
    try:
        page.wait_for_load_state('networkidle', timeout=3000)
    except Exception:
        pass  # Pages with long polling never go idle; the DOM is already usable.
    return browser, page, response


def _extract(page):
    data = page.evaluate(EXTRACT_JS)
    for item in data['elements']:
        if ':has-text(' in item['selector']:
            item['unique'] = page.locator(item['selector']).count() == 1
    return data


def _same_page(a, b):
    pa, pb = urlsplit(a), urlsplit(b)
    return _origin(a) == _origin(b) and (pa.path or '/') == (pb.path or '/') and pa.query == pb.query


def candidate_paths(url, hints=(), links=()):
    """Same-site pages worth reading: paths named in requirement text and links on the start page.

    Only GET page loads happen, and links that look like they change state (logout, delete, ...) are skipped.
    """
    found = []
    for text in hints:
        found += PATH_IN_TEXT.findall(text or '') + URL_IN_TEXT.findall(text or '')
    found += [link for link in links if link]
    paths = []
    for value in found:
        target = urljoin(url, value)
        parts = urlsplit(target)
        if parts.scheme not in ('http', 'https') or _origin(target) != _origin(url) or _same_page(target, url):
            continue
        if RISKY_LINK.search(target):
            continue
        path = (parts.path or '/') + (f'?{parts.query}' if parts.query else '')
        if path not in paths:
            paths.append(path)
    return paths[:MAX_PAGES]


def _visit(page, url, path):
    """Read one more page in the same browser; None elements when it redirected to a page already read."""
    target = urljoin(url, path)
    entry = {'path': path}
    try:
        response = page.goto(target, wait_until='domcontentloaded', timeout=15000)
        try:
            page.wait_for_load_state('networkidle', timeout=2000)
        except Exception:
            pass
    except Exception as error:
        entry['error'] = type(error).__name__
        return entry
    entry['status'] = response.status if response else None
    if not _same_page(page.url, target):
        entry['redirected_to'] = urlsplit(page.url).path or '/'
    return entry


def _capture(url, channel=None, hints=(), follow=True):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser, page, response = _open(playwright, url, channel)
        try:
            data = _extract(page)
            data.update(url=page.url, status=response.status if response else None)
            if not follow:
                return data
            links = [e.get('href') for e in data['elements'] if e['tag'] == 'a']
            data['other_pages'] = []
            read = {page.url}
            for path in candidate_paths(url, hints, links):
                entry = _visit(page, url, path)
                if 'error' not in entry and not any(_same_page(page.url, seen) for seen in read):
                    read.add(page.url)
                    extracted = _extract(page)
                    entry.update(title=extracted['title'], elements=extracted['elements'][:MAX_OTHER_ELEMENTS])
                data['other_pages'].append(entry)
            return data
        finally:
            browser.close()


def _count(page, selectors):
    result = {}
    for selector in selectors:
        try:
            result[selector] = page.locator(selector).count()
        except Exception:
            result[selector] = 'invalid'
    return result


def _check(url, selectors, channel=None, paths=()):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser, page, _ = _open(playwright, url, channel)
        try:
            result = {'start': _count(page, selectors), 'pages': {}}
            for path in paths:
                entry = _visit(page, url, path)
                if 'error' not in entry and not _same_page(page.url, url):
                    result['pages'][path] = _count(page, selectors)
            return result
        finally:
            browser.close()


def _run(mode, url, payload=None):
    from qa_system.runner import child_environment, diagnose

    command = [sys.executable, '-m', 'qa_system.page_context', mode, url]
    if os.getenv('QA_BROWSER_CHANNEL'):
        command += ['--channel', os.environ['QA_BROWSER_CHANNEL']]
    try:
        done = subprocess.run(
            command,
            cwd=ROOT,
            env=child_environment(),
            input=json.dumps(payload or {}),
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise PageContextError('페이지를 읽는 데 시간이 너무 오래 걸립니다. 주소와 네트워크를 확인하세요.')
    if done.returncode != 0:
        output = done.stdout + done.stderr
        hint = diagnose(output)
        network = re.search(r'net::ERR_[A-Z_]+', output)
        if not hint and network:
            hint = (
                f'페이지에 접속할 수 없습니다 ({network[0]}). 주소와 대상 서버가 켜져 있는지 확인하세요. '
                '로그인 데모는 start_demo.cmd로 켭니다.'
            )
        raise PageContextError(
            hint
            or '페이지 구조를 읽지 못했습니다: '
            + redact(output.strip().splitlines()[-1] if output.strip() else '알 수 없는 오류')[:300]
        )
    return json.loads(done.stdout)


def capture(url, hints=(), follow=True):
    """Structure of the start page and, with follow, of other same-site pages for the AI prompt.

    hints are texts (requirements, the user's request) whose paths such as /welcome are read too.
    """
    return _run('capture', url, {'hints': [h for h in hints if h], 'follow': follow})


def readable_paths(context):
    """Other pages whose structure was actually read (not redirected or failed)."""
    return [p['path'] for p in (context or {}).get('other_pages', []) if p.get('elements') is not None]


def check_selectors(url, selectors, paths=()):
    """Match counts per selector: {'start': {...}, 'pages': {path: {...}}}; 'invalid' when Playwright rejects one."""
    selectors = list(dict.fromkeys(s for s in selectors if s))
    if not selectors:
        return {'start': {}, 'pages': {}}
    return _run('check', url, {'selectors': selectors, 'paths': list(paths)})


def step_selectors(steps):
    return [s.get('selector', '') for s in steps if s.get('selector')]


def summarize_check(steps, checked):
    """Counts for the review screen and AI-quality measurement.

    unique: exactly one match on the start page; elsewhere: exactly one match on another page that was read.
    """
    selectors = step_selectors(steps)
    start, pages = checked.get('start', {}), checked.get('pages', {})
    summary = {
        'selectors': selectors,
        'total': len(selectors),
        'unique': 0,
        'elsewhere': {},
        'multiple': [],
        'missing': [],
        'invalid': [],
    }
    for selector in selectors:
        count = start.get(selector)
        other = {path: counts.get(selector) for path, counts in pages.items()}
        if count == 1:
            summary['unique'] += 1
        elif count == 'invalid':
            summary['invalid'].append(selector)
        elif any(c == 1 for c in other.values()):
            summary['elsewhere'][selector] = next(path for path, c in other.items() if c == 1)
        elif (isinstance(count, int) and count > 1) or any(isinstance(c, int) and c > 1 for c in other.values()):
            summary['multiple'].append(selector)
        else:
            summary['missing'].append(selector)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['capture', 'check'])
    parser.add_argument('url')
    parser.add_argument('--channel')
    args = parser.parse_args()
    payload = json.loads(sys.stdin.read() or '{}')
    if args.mode == 'capture':
        result = _capture(args.url, args.channel, payload.get('hints', ()), payload.get('follow', True))
    else:
        result = _check(args.url, payload.get('selectors', []), args.channel, payload.get('paths', ()))
    sys.stdout.write(json.dumps(redact(result), ensure_ascii=False))


if __name__ == '__main__':
    main()
