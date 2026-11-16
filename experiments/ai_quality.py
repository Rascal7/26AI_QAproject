"""Measure AI test generation quality with and without the target page's structure.

For every target page and scenario, the same request is sent to the AI under two conditions
(page structure off / on), several times. Each generated test is then
  1. checked for format (the same validation used when saving a test),
  2. checked on the real start page: does each selector match exactly one element,
  3. executed unchanged by the normal QA runner (pytest + Playwright): PASS / FAIL / ERROR,
  4. for every FAIL, triaged by the AI failure analysis. The pages behave correctly, so the right answer
     is always "test_definition"; this measures whether the analysis blames the product by mistake.

Usage:  .venv\\Scripts\\python.exe -m experiments.ai_quality [--reps 3] [--limit N] [--no-triage]
        .venv\\Scripts\\python.exe -m experiments.ai_quality --triage-from RESULT.json --db QA.db
This makes real OpenAI API calls: targets x scenarios x 2 conditions x reps, plus one per FAIL.
Results go to experiments/results/. data/qa.db is never touched (a temporary QA DB is used).
"""

import argparse
import csv
import json
import os
import platform
import tempfile
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = Path(tempfile.mkdtemp(prefix='ai-quality-'))
os.environ['QA_DB_PATH'] = str(WORK / 'qa.db')

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / '.env')  # OPENAI_API_KEY, OPENAI_MODEL, optional QA_BROWSER_CHANNEL

from flask import Flask  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402
from demo_web.app import create_app  # noqa: E402
from demo_web.seed import PASSWORD, WRONG_PASSWORD, seed  # noqa: E402

# Documented local demo account; the runner passes only QA_TEST_* variables to test processes.
os.environ['QA_TEST_PASSWORD'] = PASSWORD
os.environ['QA_TEST_WRONG_PASSWORD'] = WRONG_PASSWORD

from qa_system import failure_analysis, storage  # noqa: E402
from qa_system.ai import generate_project_cases  # noqa: E402
from qa_system.page_context import PageContextError, capture, check_selectors, step_selectors, summarize_check  # noqa: E402
from qa_system.projects import create_project, get_project, requirements, save_case, save_requirement  # noqa: E402
from qa_system.runner import run_suite  # noqa: E402

CONDITIONS = ('without', 'with')
CONDITION_LABELS = {'without': '페이지 구조 없음', 'with': '페이지 구조 전달'}
SECRETS_NOTE = ' 비밀번호 입력에는 ${QA_TEST_PASSWORD}, 틀린 비밀번호나 다른 비밀번호가 필요하면 ${QA_TEST_WRONG_PASSWORD}를 사용한다.'

TARGETS = {
    'login': dict(
        name='실험 · 로그인 데모',
        path='/login',
        overview='이메일과 비밀번호로 로그인한다. 테스트 계정 이메일은 qa.user@example.com 이다. '
        '로그인에 성공하면 /home 으로 이동해 "로그인 완료" 제목을 보여준다.' + SECRETS_NOTE,
        exceptions='빈 이메일이면 "이메일을 입력하세요.", 빈 비밀번호면 "비밀번호를 입력하세요."를 해당 입력창 아래에 표시하고 '
        '요청을 보내지 않는다. 틀린 비밀번호면 "이메일 또는 비밀번호가 올바르지 않습니다."를 표시한다.',
        scenarios=[
            (
                'empty-email',
                '빈 이메일 안내',
                '이메일 없이 로그인하면 이메일 입력창 아래에 "이메일을 입력하세요."를 표시한다.',
                '이메일을 비운 채 로그인 버튼을 누르면 이메일 오류 문구가 보이는지 확인하는 테스트 1개만 만들어줘.',
            ),
            (
                'empty-password',
                '빈 비밀번호 안내',
                '비밀번호 없이 로그인하면 비밀번호 입력창 아래에 "비밀번호를 입력하세요."를 표시한다.',
                '이메일만 입력하고 비밀번호를 비운 채 로그인하면 비밀번호 오류 문구가 보이는지 확인하는 테스트 1개만 만들어줘.',
            ),
            (
                'wrong-password',
                '잘못된 비밀번호 거부',
                '틀린 비밀번호로 로그인하면 "이메일 또는 비밀번호가 올바르지 않습니다."를 표시한다.',
                '테스트 계정에 틀린 비밀번호를 넣고 로그인하면 실패 안내가 보이는지 확인하는 테스트 1개만 만들어줘.',
            ),
            (
                'login-success',
                '정상 로그인',
                '올바른 계정으로 로그인하면 /home 으로 이동해 "로그인 완료" 제목을 보여준다.',
                '테스트 계정으로 정상 로그인하면 로그인 완료 화면으로 이동하는지 확인하는 테스트 1개만 만들어줘.',
            ),
            (
                'layout',
                '로그인 화면 구성',
                '로그인 화면에 제목, 이메일 입력창, 비밀번호 입력창, 로그인 버튼이 보인다.',
                '로그인 화면에 제목, 입력창 2개, 로그인 버튼이 모두 보이는지 확인하는 테스트 1개만 만들어줘.',
            ),
        ],
    ),
    'signup': dict(
        name='실험 · 회원가입 (data-testid 없음)',
        path='/signup',
        overview='이메일 주소, 비밀번호, 비밀번호 확인을 입력하고 이용약관에 동의한 뒤 가입한다. '
        '가입에 성공하면 /welcome 으로 이동해 "가입을 환영합니다" 제목을 보여준다.' + SECRETS_NOTE,
        exceptions='빈 이메일이면 "이메일 주소를 입력해 주세요.", 비밀번호 확인이 다르면 "비밀번호가 일치하지 않습니다.", '
        '약관에 동의하지 않으면 "이용약관 동의가 필요합니다."를 폼의 안내 영역에 표시한다.',
        scenarios=[
            (
                'empty-email',
                '빈 이메일 안내',
                '이메일 없이 가입하면 "이메일 주소를 입력해 주세요."를 표시한다.',
                '이메일을 비운 채 가입하기를 누르면 안내 문구가 보이는지 확인하는 테스트 1개만 만들어줘.',
            ),
            (
                'password-mismatch',
                '비밀번호 확인 불일치',
                '비밀번호와 비밀번호 확인이 다르면 "비밀번호가 일치하지 않습니다."를 표시한다.',
                '올바른 이메일을 넣고 비밀번호 확인을 다르게 입력해 가입하면 불일치 안내가 보이는지 확인하는 테스트 1개만 만들어줘.',
            ),
            (
                'terms-required',
                '약관 동의 필수',
                '다른 값이 모두 올바르더라도 약관에 동의하지 않으면 "이용약관 동의가 필요합니다."를 표시한다.',
                '모든 값을 올바르게 넣고 약관 동의만 하지 않은 채 가입하면 안내가 보이는지 확인하는 테스트 1개만 만들어줘.',
            ),
            (
                'signup-success',
                '정상 가입',
                '모든 값을 올바르게 입력하고 약관에 동의하면 /welcome 으로 이동해 "가입을 환영합니다"를 보여준다.',
                '올바르게 입력하고 약관에 동의해 가입하면 환영 페이지로 이동하는지 확인하는 테스트 1개만 만들어줘.',
            ),
            (
                'layout',
                '가입 화면 구성',
                '가입 화면에 제목, 이메일·비밀번호·비밀번호 확인 입력창, 약관 동의, 가입 버튼이 보인다.',
                '가입 화면에 제목, 입력창 3개, 약관 동의 체크박스, 가입 버튼이 모두 보이는지 확인하는 테스트 1개만 만들어줘.',
            ),
        ],
    ),
}


def signup_app():
    app = Flask('signup_fixture')
    page = (ROOT / 'experiments/signup_fixture.html').read_text(encoding='utf-8')
    app.add_url_rule('/signup', 'signup', lambda: page)
    app.add_url_rule(
        '/welcome',
        'welcome',
        lambda: (
            '<!doctype html><html lang="ko"><meta charset="utf-8"><title>환영</title><h1>가입을 환영합니다</h1></html>'
        ),
    )
    app.add_url_rule(
        '/login',
        'login',
        lambda: '<!doctype html><html lang="ko"><meta charset="utf-8"><title>로그인</title><h1>로그인</h1></html>',
    )
    return app


def serve(app):
    server = make_server('127.0.0.1', 0, app)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f'http://127.0.0.1:{server.server_port}'


def generate(target, scenarios, reps, records, contexts):
    """Generate under both conditions, then check selectors and save each test unchanged."""
    pid = create_project(target['name'], target['url'], target['overview'], target['exceptions'])
    started = time.perf_counter()
    contexts[target['key']] = capture(target['url'])
    contexts[target['key'] + '_seconds'] = round(time.perf_counter() - started, 2)
    for scenario_id, title, spec, prompt in scenarios:
        rid = save_requirement(pid, title, spec)
        requirement = next(r for r in requirements(pid) if r['id'] == rid)
        for condition in CONDITIONS:
            for rep in range(reps):
                base = dict(target=target['key'], scenario=scenario_id, condition=condition, rep=rep)
                started = time.perf_counter()
                try:
                    drafts = generate_project_cases(
                        get_project(pid), requirement, prompt, contexts[target['key']] if condition == 'with' else None
                    )
                except Exception as error:
                    records.append(dict(base, index=0, generation_error=type(error).__name__))
                    print('  generation error', base, type(error).__name__, flush=True)
                    continue
                seconds = round(time.perf_counter() - started, 2)
                try:
                    counts = check_selectors(target['url'], [s for d in drafts for s in step_selectors(d['steps'])])
                except PageContextError as error:
                    counts, check_error = None, str(error)
                else:
                    check_error = None
                for index, draft in enumerate(drafts):
                    record = dict(
                        base,
                        index=index,
                        generation_seconds=seconds,
                        drafts_in_response=len(drafts),
                        description=draft['description'],
                        expected=draft['expected'],
                        review_notes=draft['review_notes'],
                        steps=draft['steps'],
                        selector_check=summarize_check(draft['steps'], counts) if counts is not None else None,
                        selector_check_error=check_error,
                    )
                    try:
                        record['case_id'] = save_case(pid, rid, dict(draft), reviewed=True)
                        record['format_ok'] = True
                    except ValueError as error:
                        record['format_ok'], record['format_error'] = False, str(error)
                    records.append(record)
                print(
                    f'  {target["key"]}/{scenario_id}/{condition}/{rep}: {len(drafts)} test(s), {seconds}s', flush=True
                )
    return pid


def execute(pid, target_key, records, runs):
    """Run every saved test of a target unchanged, one run per condition."""
    for condition in CONDITIONS:
        chosen = [r for r in records if r['target'] == target_key and r['condition'] == condition and r.get('case_id')]
        if not chosen:
            continue
        run_id = run_suite([r['case_id'] for r in chosen], project_id=pid)
        runs[f'{target_key}/{condition}'] = run_id
        results = {
            r['case_id']: r
            for r in storage.rows('SELECT case_id,outcome,details FROM test_results WHERE run_id=?', (run_id,))
        }
        for record in chosen:
            result = results.get(record['case_id'])
            record['run_id'] = run_id
            record['outcome'] = result['outcome'] if result else 'ERROR'
            if result and result['outcome'] != 'PASS':
                record['run_error'] = (json.loads(result['details']).get('error') or '')[:300]
        print(f'  executed {target_key}/{condition}: run {run_id}', flush=True)


def triage(records, runs, force=False):
    """AI failure analysis of every FAIL; the pages are correct, so the expected class is test_definition."""
    failure_analysis.MAX_PER_RUN = 10_000
    if force:
        for record in records:
            if record.get('triage'):
                record['triage_previous'] = record['triage']
    by_case = {}
    for run_id in runs.values():
        _, errors = failure_analysis.analyze_run(run_id, force=force)
        for error in errors:
            print('  triage error', error, flush=True)
        for row in storage.rows(
            'SELECT r.case_id,b.ai_analysis FROM bug_reports b JOIN test_results r ON b.result_id=r.id '
            'WHERE r.run_id=?',
            (run_id,),
        ):
            by_case[row['case_id']] = json.loads(row['ai_analysis']) if row['ai_analysis'] else None
    for record in records:
        if record.get('outcome') == 'FAIL':
            analysis = by_case.get(record.get('case_id'))
            record['triage'] = (
                {k: analysis[k] for k in ('likely_cause', 'confidence', 'suggested_action')} if analysis else None
            )
    print(f'  triaged {sum(bool(r.get("triage")) for r in records)} failure(s)', flush=True)


def ratio(numerator, denominator):
    return f'{numerator}/{denominator} ({100 * numerator / denominator:.1f}%)' if denominator else '—'


def summarize(rows):
    checks = [r['selector_check'] for r in rows if r.get('selector_check')]
    generated = [r for r in rows if not r.get('generation_error')]
    total = sum(c['total'] for c in checks)
    return dict(
        requests=len({(r['target'], r['scenario'], r['rep']) for r in rows}),
        generation_errors=sum(bool(r.get('generation_error')) for r in rows),
        generated=len(generated),
        format_ok=sum(bool(r.get('format_ok')) for r in generated),
        selectors=total,
        selectors_unique=sum(c['unique'] for c in checks),
        selectors_missing=sum(len(c['missing']) for c in checks),
        selectors_multiple=sum(len(c['multiple']) for c in checks),
        selectors_invalid=sum(len(c['invalid']) for c in checks),
        tests_all_selectors_unique=sum(bool(c['total']) and c['unique'] == c['total'] for c in checks),
        passed=sum(r.get('outcome') == 'PASS' for r in generated),
        failed=sum(r.get('outcome') == 'FAIL' for r in generated),
        errors=sum(r.get('outcome') == 'ERROR' for r in generated),
        mean_generation_seconds=round(sum(r['generation_seconds'] for r in generated) / len(generated), 2)
        if generated
        else None,
    )


def report(meta, records, contexts):
    lines = [
        '# AI 테스트 생성 품질 측정 — 페이지 구조 전달 효과',
        '',
        f'- 실행: {meta["started"]} (한국 시간) · 모델: `{meta["model"]}` · 반복: {meta["reps"]}회 · 브라우저: {meta["browser"]}',
        f'- 대상: {", ".join(TARGETS[t]["name"] for t in meta["targets"])} · 시나리오: 대상별 {meta["scenarios_per_target"]}개',
        '- 조건: 같은 요구사항·요청 문장을 **페이지 구조 없음** / **페이지 구조 전달** 두 조건으로 AI에 보냄. 요청 문장에는 선택자를 넣지 않음.',
        '- 판정: 생성된 테스트를 **수정하지 않고** 저장(형식 검사) → 시작 페이지에서 선택자 확인 → QA 실행기로 실제 실행.',
        '',
        '## 전체 결과',
        '',
        '| 지표 | ' + ' | '.join(CONDITION_LABELS[c] for c in CONDITIONS) + ' |',
        '|---|' + '---|' * len(CONDITIONS),
    ]
    overall = {c: summarize([r for r in records if r['condition'] == c]) for c in CONDITIONS}
    rows = [
        ('생성된 테스트', lambda s: str(s['generated'])),
        ('형식 검사 통과', lambda s: ratio(s['format_ok'], s['generated'])),
        ('시작 페이지에서 정확히 1개와 일치한 선택자', lambda s: ratio(s['selectors_unique'], s['selectors'])),
        ('시작 페이지에 없는 선택자', lambda s: ratio(s['selectors_missing'], s['selectors'])),
        ('여러 요소와 일치한 선택자', lambda s: ratio(s['selectors_multiple'], s['selectors'])),
        ('선택자 문법 오류', lambda s: ratio(s['selectors_invalid'], s['selectors'])),
        ('모든 선택자가 정확히 일치한 테스트', lambda s: ratio(s['tests_all_selectors_unique'], s['generated'])),
        ('**수정 없이 실행해 PASS**', lambda s: ratio(s['passed'], s['generated'])),
        ('FAIL (기대와 다른 동작·잘못된 단계)', lambda s: ratio(s['failed'], s['generated'])),
        ('ERROR (실행 불가)', lambda s: ratio(s['errors'], s['generated'])),
        ('평균 생성 시간(초)', lambda s: str(s['mean_generation_seconds'])),
        ('AI 호출 실패', lambda s: str(s['generation_errors'])),
    ]
    lines += [f'| {label} | ' + ' | '.join(fn(overall[c]) for c in CONDITIONS) + ' |' for label, fn in rows]
    for target in meta['targets']:
        lines += [
            '',
            f'## {TARGETS[target]["name"]}',
            '',
            f'페이지 구조: 요소 {len(contexts[target]["elements"])}개, 읽기 {meta.get("capture_seconds", {}).get(target, "—")}초',
            '',
            '| 시나리오 | '
            + ' | '.join(f'{CONDITION_LABELS[c]} PASS' for c in CONDITIONS)
            + ' | '
            + ' | '.join(f'{CONDITION_LABELS[c]} 선택자 일치' for c in CONDITIONS)
            + ' |',
            '|---|' + '---|' * (2 * len(CONDITIONS)),
        ]
        for scenario_id, title, _, _ in TARGETS[target]['scenarios'][: meta['scenarios_per_target']]:
            cells = {
                c: summarize(
                    [
                        r
                        for r in records
                        if r['target'] == target and r['scenario'] == scenario_id and r['condition'] == c
                    ]
                )
                for c in CONDITIONS
            }
            lines.append(
                f'| {title} | '
                + ' | '.join(ratio(cells[c]['passed'], cells[c]['generated']) for c in CONDITIONS)
                + ' | '
                + ' | '.join(ratio(cells[c]['selectors_unique'], cells[c]['selectors']) for c in CONDITIONS)
                + ' |'
            )
    triaged = [r for r in records if r.get('outcome') == 'FAIL']
    if any(r.get('triage') for r in triaged):
        lines += [
            '',
            '## AI 실패 분석의 원인 분류',
            '',
            '대상 페이지는 정상이므로 모든 FAIL의 정답은 **테스트 정의 문제**입니다. 제품 결함으로 분류하면 오판입니다.',
            '',
            '| 분류 | ' + ' | '.join(CONDITION_LABELS[c] for c in CONDITIONS) + ' | 합계 |',
            '|---|' + '---|' * (len(CONDITIONS) + 1),
        ]
        for cause, label in [*failure_analysis.CAUSE_LABELS.items(), (None, '분석 실패')]:
            counts = [
                sum((r.get('triage') or {}).get('likely_cause') == cause for r in triaged if r['condition'] == c)
                for c in CONDITIONS
            ]
            lines.append(f'| {label} | ' + ' | '.join(map(str, counts)) + f' | {sum(counts)} |')
        correct = sum((r.get('triage') or {}).get('likely_cause') == 'test_definition' for r in triaged)
        lines += ['', f'정답(테스트 정의 문제) 비율: {ratio(correct, len(triaged))}']
        previous = [r['triage_previous'] for r in triaged if r.get('triage_previous')]
        if previous:
            before = sum(p.get('likely_cause') == 'test_definition' for p in previous)
            lines += [
                '',
                f'분석 지시문 보강 전 같은 실패에 대한 정답 비율: {ratio(before, len(previous))}. '
                '같은 표본으로 고쳤으므로, 실제 결함 인식은 triage-faults 결과로 함께 확인합니다.',
            ]
        lines += ['', '| 대상 | 시나리오 | 조건 | AI 분류 | AI 제안 |', '|---|---|---|---|---|']
        for r in triaged:
            t = r.get('triage') or {}
            cause = failure_analysis.CAUSE_LABELS.get(t.get('likely_cause'), '분석 실패')
            action = ' '.join((t.get('suggested_action') or '').split()).replace('|', '/')
            lines.append(
                f'| {r["target"]} | {r["scenario"]} | {CONDITION_LABELS[r["condition"]]} | {cause} | {action} |'
            )
    lines += [
        '',
        '## 해석 시 주의',
        '',
        '- 대상 페이지는 정상 동작하도록 만든 페이지입니다. 여기서 FAIL은 제품 결함이 아니라 **AI가 만든 테스트가 틀렸다**는 뜻입니다(잘못된 선택자, 단계 누락, 기대 문구 오류 등).',
        '- 선택자 일치는 **시작 페이지** 기준입니다. 페이지 이동 뒤에 나타나는 요소(예: 로그인 후 제목)는 정상이어도 "없음"으로 집계됩니다. 두 조건에 같은 기준을 적용합니다.',
        '- 회원가입 페이지는 이 실험용으로 만든 페이지로, `data-testid`가 없고 id·name이 관례와 다릅니다. 선택자를 짐작하기 어려운 실제 사이트를 흉내 냅니다.',
        '- 요청마다 AI가 테스트를 여러 개 돌려줄 수 있어 생성 수가 요청 수보다 많을 수 있습니다.',
        '- 기획서의 "유효 TC 비율"(요구사항에 맞는 의미 있는 테스트인지)은 사람이 판단해야 합니다. 같은 폴더의 CSV `수동 판정` 열에 유효/중복/오류를 기록하세요.',
        '- 수동 작성 시간과의 비교는 이 스크립트로 측정하지 않습니다.',
    ]
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--reps', type=int, default=3, help='조건별 반복 횟수')
    parser.add_argument('--limit', type=int, default=None, help='대상별 시나리오 수 제한(시범 실행용)')
    parser.add_argument('--targets', nargs='+', choices=list(TARGETS), default=list(TARGETS))
    parser.add_argument('--out', default=str(ROOT / 'experiments/results'))
    parser.add_argument('--no-triage', action='store_true', help='FAIL의 AI 원인 분석을 건너뜁니다.')
    parser.add_argument('--triage-from', help='이미 끝난 실험 결과(.json)에 원인 분석만 추가합니다. --db 필요.')
    parser.add_argument('--db', help='--triage-from 실험이 사용한 임시 QA DB 경로')
    parser.add_argument(
        '--retriage', action='store_true', help='--triage-from 에서 이미 분석한 실패도 다시 분석합니다(이전 결과 보존).'
    )
    args = parser.parse_args()
    if not os.getenv('OPENAI_API_KEY'):
        raise SystemExit('.env에 OPENAI_API_KEY가 필요합니다.')
    if args.triage_from:
        if not args.db or not Path(args.db).exists():
            raise SystemExit('--triage-from 에는 실험이 사용한 QA DB(--db)가 필요합니다.')
        storage.QA_DB = Path(args.db)
        data = json.loads(Path(args.triage_from).read_text(encoding='utf-8'))
        triage(data['records'], data['meta']['runs'], force=args.retriage)
        write_outputs(Path(args.triage_from).with_suffix(''), data['meta'], data['records'], data['page_contexts'])
        return
    storage.initialize()
    started = datetime.now(timezone(timedelta(hours=9)))
    seed(WORK / 'demo.db')
    servers = {'login': serve(create_app(WORK / 'demo.db', testing=True)), 'signup': serve(signup_app())}
    records, contexts, runs = [], {}, {}
    try:
        print('QA DB (재분석용):', storage.QA_DB, flush=True)
        for key in args.targets:
            target = dict(TARGETS[key], key=key, url=servers[key][1] + TARGETS[key]['path'])
            scenarios = target['scenarios'][: args.limit]
            print(
                f'[{key}] generating: {len(scenarios)} scenarios x {len(CONDITIONS)} conditions x {args.reps} reps',
                flush=True,
            )
            pid = generate(target, scenarios, args.reps, records, contexts)
            print(f'[{key}] executing generated tests', flush=True)
            execute(pid, key, records, runs)
        if not args.no_triage:
            print('triaging failures', flush=True)
            triage(records, runs)
    finally:
        for server, _ in servers.values():
            server.shutdown()
    meta = dict(
        started=started.strftime('%Y-%m-%d %H:%M'),
        model=os.getenv('OPENAI_MODEL', 'gpt-4.1-mini'),
        reps=args.reps,
        targets=args.targets,
        scenarios_per_target=args.limit or 5,
        browser=os.getenv('QA_BROWSER_CHANNEL') or 'Playwright Chromium',
        runs=runs,
        python=platform.python_version(),
        capture_seconds={k[: -len('_seconds')]: v for k, v in contexts.items() if k.endswith('_seconds')},
    )
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = out / ('ai-quality-' + started.strftime('%Y%m%d-%H%M'))
    write_outputs(stem, meta, records, {k: v for k, v in contexts.items() if not k.endswith('_seconds')})


def write_outputs(stem, meta, records, contexts):
    summary = {c: summarize([r for r in records if r['condition'] == c]) for c in CONDITIONS}
    stem.with_suffix('.json').write_text(
        json.dumps(
            dict(meta=meta, summary=summary, records=records, page_contexts=contexts), ensure_ascii=False, indent=2
        ),
        encoding='utf-8',
    )
    stem.with_suffix('.md').write_text(report(meta, records, contexts), encoding='utf-8')
    with stem.with_suffix('.csv').open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                '대상',
                '시나리오',
                '조건',
                '반복',
                '번호',
                '테스트 이름',
                '실행 결과',
                '선택자 일치',
                '단계',
                '오류',
                'AI 원인 분류',
                '수동 판정(유효/중복/오류)',
                '메모',
            ]
        )
        for r in records:
            check = r.get('selector_check') or {}
            writer.writerow(
                [
                    r['target'],
                    r['scenario'],
                    CONDITION_LABELS[r['condition']],
                    r['rep'] + 1,
                    r['index'] + 1,
                    r.get('description', ''),
                    r.get('outcome', r.get('generation_error', '')),
                    f'{check.get("unique", "")}/{check.get("total", "")}' if check else '',
                    json.dumps(r.get('steps', []), ensure_ascii=False),
                    r.get('format_error') or r.get('run_error') or '',
                    failure_analysis.CAUSE_LABELS.get((r.get('triage') or {}).get('likely_cause'), ''),
                    '',
                    '',
                ]
            )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print('결과:', stem.with_suffix('.md'))


if __name__ == '__main__':
    main()
