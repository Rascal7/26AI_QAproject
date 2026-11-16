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
from urllib.parse import urlsplit
from demo_web.db import ROOT
from qa_system.evidence import redact

MAX_ELEMENTS = 80
TIMEOUT = 45

# Collects interactive and landmark elements with the most stable selector that matches exactly one element.
EXTRACT_JS = r'''
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
'''.replace('MAX', str(MAX_ELEMENTS))


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


def _capture(url, channel=None):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser, page, response = _open(playwright, url, channel)
        try:
            data = page.evaluate(EXTRACT_JS)
            for item in data['elements']:
                if ':has-text(' in item['selector']:
                    item['unique'] = page.locator(item['selector']).count() == 1
            data.update(url=page.url, status=response.status if response else None)
            return data
        finally:
            browser.close()


def _check(url, selectors, channel=None):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser, page, _ = _open(playwright, url, channel)
        try:
            result = {}
            for selector in selectors:
                try:
                    result[selector] = page.locator(selector).count()
                except Exception:
                    result[selector] = 'invalid'
            return result
        finally:
            browser.close()


def _run(mode, url, payload=None):
    from qa_system.runner import child_environment, diagnose
    command = [sys.executable, '-m', 'qa_system.page_context', mode, url]
    if os.getenv('QA_BROWSER_CHANNEL'):
        command += ['--channel', os.environ['QA_BROWSER_CHANNEL']]
    try:
        done = subprocess.run(command, cwd=ROOT, env=child_environment(), input=json.dumps(payload or []),
                              capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        raise PageContextError('페이지를 읽는 데 시간이 너무 오래 걸립니다. 주소와 네트워크를 확인하세요.')
    if done.returncode != 0:
        output = done.stdout + done.stderr
        hint = diagnose(output)
        network = re.search(r'net::ERR_[A-Z_]+', output)
        if not hint and network:
            hint = (f'페이지에 접속할 수 없습니다 ({network[0]}). 주소와 대상 서버가 켜져 있는지 확인하세요. '
                    '로그인 데모는 start_demo.cmd로 켭니다.')
        raise PageContextError(hint or '페이지 구조를 읽지 못했습니다: ' + redact(output.strip().splitlines()[-1] if output.strip() else '알 수 없는 오류')[:300])
    return json.loads(done.stdout)


def capture(url):
    """Visible structure of the page at url, for the AI prompt."""
    return _run('capture', url)


def check_selectors(url, selectors):
    """Match count of each selector on the page at url ('invalid' when Playwright rejects it)."""
    selectors = list(dict.fromkeys(s for s in selectors if s))
    return _run('check', url, selectors) if selectors else {}


def step_selectors(steps):
    return [s.get('selector', '') for s in steps if s.get('selector')]


def summarize_check(steps, counts):
    """Counts for the review screen and later AI-quality measurement."""
    selectors = step_selectors(steps)
    status = [counts.get(s) for s in selectors]
    return {'selectors': selectors, 'total': len(selectors),
            'unique': sum(c == 1 for c in status),
            'multiple': [s for s, c in zip(selectors, status) if isinstance(c, int) and c > 1],
            'missing': [s for s, c in zip(selectors, status) if c == 0],
            'invalid': [s for s, c in zip(selectors, status) if c == 'invalid']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['capture', 'check'])
    parser.add_argument('url')
    parser.add_argument('--channel')
    args = parser.parse_args()
    if args.mode == 'capture':
        result = _capture(args.url, args.channel)
    else:
        result = _check(args.url, json.loads(sys.stdin.read() or '[]'), args.channel)
    sys.stdout.write(json.dumps(redact(result), ensure_ascii=False))


if __name__ == '__main__':
    main()
