import json
import sqlite3
import threading
from unittest.mock import patch
import pytest
from streamlit.testing.v1 import AppTest
from qa_system import background, failure_analysis, storage
from qa_system.projects import create_project, save_requirement, save_case

STEPS = [
    {'action': 'navigate', 'selector': '', 'value': ''},
    {'action': 'assert_text', 'selector': '#msg', 'value': '환영합니다'},
]
ANSWER = dict(
    observed_facts=['#msg 요소를 찾지 못함'],
    likely_cause='test_definition',
    confidence='high',
    hypotheses=['선택자를 추정함'],
    suggested_checks=['페이지에서 안내 영역 확인'],
    suggested_action='assert_text 선택자를 #join-msg로 바꾸세요.',
)


@pytest.fixture
def failed_run(tmp_path, monkeypatch):
    path = tmp_path / 'qa.db'
    monkeypatch.setattr(storage, 'QA_DB', path)
    storage.initialize()
    pid = create_project('가입 페이지', 'http://127.0.0.1:9999/signup', '가입한다', '오류 안내')
    rid = save_requirement(pid, '가입 안내', '가입하면 환영 문구를 보여준다')
    case = dict(
        engine='web',
        source='ai',
        description='환영 문구',
        expected='환영합니다 표시',
        steps=STEPS,
        review_notes='선택자를 추정했습니다.',
        selector_check={'missing': ['#msg'], 'total': 1, 'unique': 0},
    )
    case_id = save_case(pid, rid, case, reviewed=True)
    detail = dict(
        case_id=case_id,
        outcome='FAIL',
        error="Locator expected to contain text '환영합니다'",
        http=[{'endpoint': '/signup', 'status': 200}],
        observations=['1. navigate 확인'],
        evidence={'screenshot': 'C:\\Users\\someone\\shot.png'},
        expected=dict(case, id=case_id, requirement_id=rid),
    )
    with sqlite3.connect(path) as db:
        db.execute(
            "INSERT INTO test_runs(run_id,project_id,started_at,status,snapshots) VALUES('run1',?,'2026-11-16T00:00:00+00:00','COMPLETED','{}')",
            (pid,),
        )
        for n in range(2):
            result = db.execute(
                "INSERT INTO test_results(run_id,case_id,setup_status,outcome,details) VALUES('run1',?,'ready','FAIL',?)",
                (case_id, json.dumps(detail, ensure_ascii=False)),
            ).lastrowid
            db.execute(
                "INSERT INTO bug_reports(result_id,title,facts,hypothesis) VALUES(?,?,?,'원인 미확정')",
                (result, f'환영 문구 {n}', json.dumps(detail, ensure_ascii=False)),
            )
        db.execute("INSERT INTO reports(run_id,markdown) VALUES('run1','# 보고서')")
    return dict(project_id=pid, requirement_id=rid)


def test_evidence_has_requirement_steps_and_review_signals_but_no_local_paths(failed_run):
    evidence = failure_analysis.failure_evidence(failure_analysis.failures('run1')[0])
    assert evidence['requirement']['spec'] == '가입하면 환영 문구를 보여준다'
    assert evidence['project']['overview'] == '가입한다'
    assert evidence['test']['steps'] == STEPS and evidence['test']['source'] == 'ai'
    assert evidence['test']['selector_check']['missing'] == ['#msg']
    assert 'shot.png' not in json.dumps(evidence, ensure_ascii=False)


def test_blind_evidence_hides_every_fault_hint(failed_run):
    bug = failure_analysis.failures('run1')[0]
    facts = json.loads(bug['facts'])
    facts['expected'].update(fault_variant='skip_disabled', description='[결함 재현] 비활성 계정으로 로그인 성공')
    facts['target_variant'] = 'skip_disabled'
    bug = dict(bug, facts=json.dumps(facts, ensure_ascii=False), title='[결함 재현] 비활성 계정으로 로그인 성공')
    with sqlite3.connect(storage.QA_DB) as db:
        db.execute("UPDATE requirements SET exceptions='의도적으로 결함을 주입한 테스트입니다.'")
    open_evidence = json.dumps(failure_analysis.failure_evidence(bug), ensure_ascii=False)
    blind = json.dumps(failure_analysis.failure_evidence(bug, blind=True), ensure_ascii=False)
    assert 'skip_disabled' in open_evidence and '결함' in open_evidence
    assert 'skip_disabled' not in blind and '결함' not in blind
    assert '가입하면 환영 문구를 보여준다' in blind  # the requirement itself stays


def test_analyze_run_stores_each_failure_and_continues_after_an_api_error(failed_run):
    with patch(
        'qa_system.failure_analysis.request_parsed',
        side_effect=[RuntimeError('rate limit'), failure_analysis.FailureAnalysis(**ANSWER)],
    ) as call:
        analysed, errors = failure_analysis.analyze_run('run1')
    assert analysed == 1 and errors == ['환영 문구 0: RuntimeError']
    assert call.call_args.args[0] is failure_analysis.FailureAnalysis
    bugs = failure_analysis.failures('run1')
    assert bugs[0]['ai_analysis'] is None and bugs[0]['hypothesis'] == '원인 미확정'
    assert json.loads(bugs[1]['ai_analysis'])['likely_cause'] == 'test_definition'
    assert bugs[1]['hypothesis'].startswith('테스트 정의 문제 · ')
    with patch(
        'qa_system.failure_analysis.request_parsed', return_value=failure_analysis.FailureAnalysis(**ANSWER)
    ) as call:
        assert failure_analysis.analyze_run('run1') == (1, [])  # only the one still pending
    assert call.call_count == 1
    appendix = failure_analysis.analysis_markdown('run1')
    assert '## AI 실패 분석' in appendix and '#join-msg' in appendix and '확신도 높음' in appendix


def test_analysis_per_run_is_bounded(failed_run, monkeypatch):
    monkeypatch.setattr(failure_analysis, 'MAX_PER_RUN', 1)
    with patch(
        'qa_system.failure_analysis.request_parsed', return_value=failure_analysis.FailureAnalysis(**ANSWER)
    ) as call:
        failure_analysis.analyze_run('run1')
    assert call.call_count == 1


def _history_app(project_id):
    app = AppTest.from_string(
        'from qa_system.project_ui import history_page\nfrom qa_system.projects import get_project\n'
        f'history_page(get_project({project_id}))\n',
        default_timeout=15,
    )
    app.session_state[f'selected_run_{project_id}'] = 'run1'
    return app


def test_history_shows_analysis_and_offers_button_for_pending(failed_run, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    app = _history_app(failed_run['project_id']).run()
    assert not app.exception
    button = app.button(key='analyze_run1')
    assert button.label == 'AI 원인 분석 · 2건'
    with patch('qa_system.failure_analysis.request_parsed', return_value=failure_analysis.FailureAnalysis(**ANSWER)):
        button.click().run()
    assert not app.exception
    assert sum('테스트 정의 문제' in w.value for w in app.warning) == 2
    assert not [b for b in app.button if b.key == 'analyze_run1']


def test_failed_run_is_analysed_automatically_after_execution(failed_run, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    pid = failed_run['project_id']
    app = AppTest.from_string(
        'from qa_system.project_ui import execution_page\nfrom qa_system.projects import get_project\n'
        f'execution_page(get_project({pid}))\n',
        default_timeout=15,
    ).run()
    assert app.checkbox(key=f'auto_analyze_{pid}').value is True
    monkeypatch.setattr(background, '_jobs', {})
    gate = threading.Event()

    def fake_run(selected, variant, project_id, progress):
        progress(0, len(selected))
        gate.wait(10)  # hold the run open so the page can be checked while it is in progress
        progress(len(selected), len(selected))
        return 'run1'

    with (
        patch('qa_system.background.run_suite', side_effect=fake_run) as run,
        patch(
            'qa_system.failure_analysis.request_parsed', return_value=failure_analysis.FailureAnalysis(**ANSWER)
        ) as call,
    ):
        next(b for b in app.button if b.label == '▶ 테스트 실행').click().run()
        assert not app.exception
        # The page returned while the run is still going, and offers no second run.
        assert any('다른 화면으로 이동해도 실행은 계속됩니다' in c.value for c in app.caption)
        app.run()
        assert next(b for b in app.button if b.label == '▶ 테스트 실행').disabled
        job_id = app.session_state[f'run_job_{pid}']
        gate.set()
        assert background.wait(job_id, timeout=10)['phase'] == 'finished'
        app.run()
    assert not app.exception
    assert run.call_args.kwargs['project_id'] == pid
    assert call.call_count == 2
    assert all(b['ai_analysis'] for b in failure_analysis.failures('run1'))
    assert app.session_state[f'selected_run_{pid}'] == 'run1'
    assert any(s.value == '실행 완료' for s in app.success)
    assert not next(b for b in app.button if b.label == '▶ 테스트 실행').disabled


def test_auto_analysis_is_off_without_api_key(failed_run, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    pid = failed_run['project_id']
    app = AppTest.from_string(
        'from qa_system.project_ui import execution_page\nfrom qa_system.projects import get_project\n'
        f'execution_page(get_project({pid}))\n',
        default_timeout=15,
    ).run()
    box = app.checkbox(key=f'auto_analyze_{pid}')
    assert box.value is False and box.disabled
