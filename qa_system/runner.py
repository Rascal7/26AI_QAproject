import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
from demo_web.app import VARIANTS
from demo_web.db import ROOT, connect
from qa_system.ai import canonical_code, validate_code
from qa_system.catalog import CASES, SCENARIOS, TARGET, validate_case
from qa_system.evidence import redact
from qa_system.storage import QA_DB, initialize, get_case, now, encode, rows
from qa_system.reporting import build_report


def child_environment():
    # Allowlist: do not inherit API keys, dotenv loading, cloud credentials or arbitrary pytest hooks.
    names = ('SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATH', 'PATHEXT', 'TEMP', 'TMP',
             'USERPROFILE', 'LOCALAPPDATA', 'APPDATA', 'PROGRAMFILES', 'PROGRAMFILES(X86)',
             'PLAYWRIGHT_BROWSERS_PATH')
    env = {name: os.environ[name] for name in names if name in os.environ}
    env.update({k:v for k,v in os.environ.items() if k.startswith('QA_TEST_')})
    env.update(PYTHONUTF8='1', PYTHONPATH=str(ROOT), PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    return env


def run_suite(case_ids=None, variant='normal', reviewed_codes=None, project_id=1):
    initialize()
    from qa_system.projects import get_project
    from qa_system.web_tests import validate_steps
    project = get_project(project_id)
    if variant not in VARIANTS:
        raise ValueError('허용되지 않은 대상 버전')
    selected = list(dict.fromkeys(CASES if case_ids is None else case_ids))
    if not selected:
        raise ValueError('테스트를 선택하세요.')
    definitions = [get_case(case_id) for case_id in selected]
    owned = {r['id']:r for r in rows('SELECT id,reviewed FROM test_cases WHERE project_id=?', (project_id,))}
    if any(c not in owned for c in selected):
        raise ValueError('다른 프로젝트의 테스트는 함께 실행할 수 없습니다.')
    if project['mode'] != 'demo' and variant != 'normal':
        raise ValueError('결함 실험은 로그인 데모 전용입니다.')
    sources = []
    for i, case in enumerate(definitions):
        fault = case.get('fault_variant')
        if 'fault_variant' in case and (project['mode'] != 'demo' or
                case.get('engine') == 'web' or fault not in VARIANTS[1:]):
            raise ValueError('허용되지 않은 결함 재현 버전입니다.')
        if case.get('engine') == 'web':
            if not owned[case['id']]['reviewed']:
                raise ValueError('테스트 내용을 검토하고 승인하세요.')
            validate_steps(case['steps'], project['target_url'])
            sources.append('from qa_system.web_tests import execute_web_case\n'
                           f'def test_case_{i}(web_env):\n    execute_web_case(web_env, {case!r}, {project["target_url"]!r})\n')
            continue
        baseline = case.get('baseline_id', case['id'])
        checked = dict(case, requirement_id=CASES.get(baseline,{}).get('requirement_id'))
        if project['mode'] != 'demo' or validate_case(checked):
            raise ValueError('테스트 계약 또는 프로젝트 유형이 일치하지 않습니다.')
        if case.get('source') == 'ai':
            code = (reviewed_codes or {}).get(case['id'])
            if not code:
                raise ValueError(f"{case['id']}: Python 코드 검토·승인 후 실행하세요.")
            code = validate_code(code, baseline)
        else:
            code = canonical_code(baseline)
        decorator = f'@pytest.mark.parametrize("qa_env", [{fault!r}], indirect=True)\n' if fault else ''
        generated = code.replace('def test_generated(', decorator + f'def test_case_{i}(')
        sources.append(('import pytest\n' if fault else '') + generated)
    code_snapshot = '\n\n'.join(sources)
    run_id = uuid.uuid4().hex[:16]
    out = ROOT / 'artifacts' / run_id
    out.mkdir(parents=True)
    test_file = out / 'test_selected.py'
    test_file.write_text(code_snapshot, encoding='utf-8')
    source_hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                     for directory in ('demo_web', 'tests', 'qa_system')
                     for p in (ROOT / directory).rglob('*.py') if '__pycache__' not in p.parts}
    snapshots = {'cases': definitions, 'scenarios': SCENARIOS, 'source_sha256': source_hashes,
        'project': project,
        'saved_requirements': rows('SELECT id,spec,version,exceptions FROM requirements WHERE project_id=? ORDER BY id',(project_id,)),
        'requirements': redact((ROOT / 'LOGIN_DEMO_WEB_PLAN.md').read_text(encoding='utf-8')),
        'assertions': (ROOT / 'qa_system/contracts.py').read_text(encoding='utf-8'),
        'fixtures': (ROOT / 'tests/db_scenarios.py').read_text(encoding='utf-8')}
    with connect(QA_DB) as db:
        db.execute('INSERT INTO test_runs VALUES(?,?,?,?,?,?,?,?,?,?)',
                   (run_id, project_id, project['target_url'], variant, '1.0', now(), None, 'RUNNING', encode(snapshots), code_snapshot))
    command = [sys.executable, '-m', 'pytest', '-p', 'pytest_playwright.pytest_playwright', '-p', 'tests.conftest',
               str(test_file), '--confcutdir', str(out), '--variant', variant,
               '--result-dir', str(out), '--qa-port', '0', '--browser', 'chromium', '--tb=no',
               '--basetemp', str(out / 'tmp'), '-p', 'no:cacheprovider']
    infrastructure_error = None
    try:
        process = subprocess.Popen(command, cwd=ROOT, env=child_environment(), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace',
            start_new_session=os.name != 'nt')
        try:
            stdout, stderr = process.communicate(timeout=max(90, len(selected)*35))
        except subprocess.TimeoutExpired:
            infrastructure_error = '실행 제한 시간을 초과했습니다.'
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, timeout=15)
            else:
                import signal
                os.killpg(process.pid, signal.SIGKILL)
            process.kill()
            stdout, stderr = process.communicate(timeout=10)
        (out / 'pytest.log').write_text(redact(stdout + stderr), encoding='utf-8')
        if not infrastructure_error and process.returncode not in (0, 1):
            infrastructure_error = f'pytest 실행 오류 (exit {process.returncode}); pytest.log 확인'
    except OSError as exc:
        infrastructure_error = f'실행기를 시작하지 못했습니다: {type(exc).__name__}'
    any_error = bool(infrastructure_error)
    with connect(QA_DB) as db:
        for i, case in enumerate(definitions):
            result_file = out / f'test_case_{i}.json'
            if result_file.exists():
                detail = json.loads(result_file.read_text(encoding='utf-8'))
            else:
                detail = dict(setup_status='failed', outcome='ERROR',
                              error=infrastructure_error or '테스트 결과가 생성되지 않았습니다. pytest.log 확인', http=[], expected=case)
            if infrastructure_error:
                detail.update(outcome='ERROR', error=infrastructure_error)
            any_error = any_error or detail['outcome'] == 'ERROR'
            detail['case_id'] = case['id']
            detail['scenario_id'] = case['scenario_id']
            detail['expected'] = case
            cursor = db.execute('INSERT INTO test_results(run_id,case_id,scenario_id,setup_status,outcome,details) VALUES(?,?,?,?,?,?)',
                (run_id, case['id'], case['scenario_id'], detail['setup_status'], detail['outcome'], encode(detail)))
            if detail['outcome'] == 'FAIL':
                db.execute('INSERT INTO bug_reports(result_id,title,facts,hypothesis) VALUES(?,?,?,?)',
                    (cursor.lastrowid, case['description'], encode(detail), '원인 미확정. HTTP·세션·DB 증거 확인 필요.'))
        db.execute('UPDATE test_runs SET finished_at=?,status=? WHERE run_id=?',
                   (now(), 'ERROR' if any_error else 'COMPLETED', run_id))
    report = build_report(run_id)
    (out / 'report.md').write_text(report, encoding='utf-8')
    with connect(QA_DB) as db:
        db.execute('INSERT INTO reports VALUES(?,?,NULL)', (run_id, report))
    return run_id


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--variant', choices=VARIANTS, default='normal')
    parser.add_argument('--reverse', action='store_true')
    args = parser.parse_args()
    result_id = run_suite(list(reversed(CASES)) if args.reverse else None, args.variant)
    print(build_report(result_id).split('##')[0])
    print(f'보고서: {ROOT / "artifacts" / result_id / "report.md"}')
