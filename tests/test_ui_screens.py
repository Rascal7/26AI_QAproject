import csv
import io
import json
from unittest.mock import patch
import pytest
from streamlit.testing.v1 import AppTest
from demo_web.db import ROOT, connect
from qa_system import storage
from qa_system.project_ui import format_duration, runs_csv, short_id
from qa_system.projects import create_project, save_case, save_requirement
from qa_system.web_tests import template_cases


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'QA_DB', tmp_path / 'qa.db')
    storage.initialize()
    pid = create_project('가입 페이지', 'https://example.com/signup', '가입한다', '오류 안내', tags='가입')
    rid = save_requirement(pid, '빈 이메일', '오류 문구를 보여준다')
    # Two not-yet-approved tests with one PASS and one FAIL result in run r1.
    passed, failed = (
        save_case(pid, rid, dict(template_cases()[kind], engine='web'), reviewed=False) for kind in ('text', 'click')
    )
    with connect(storage.QA_DB) as db:
        db.execute(
            'INSERT INTO test_runs(run_id,project_id,target_url,variant,seed_version,started_at,finished_at,status,snapshots,code_snapshot) '
            "VALUES('r1',?,?,'normal','1.0','2026-11-17T01:00:00+00:00','2026-11-17T01:01:14+00:00','COMPLETED','{}','')",
            (pid, 'https://example.com/signup'),
        )
        for case_id, outcome in ((passed, 'PASS'), (failed, 'FAIL')):
            db.execute(
                "INSERT INTO test_results(run_id,case_id,setup_status,outcome,details) VALUES('r1',?,'ready',?,'{}')",
                (case_id, outcome),
            )
    return pid, rid


def app_for(script, **state):
    app = AppTest.from_string(script, default_timeout=15)
    for key, value in state.items():
        app.session_state[key] = value
    return app.run()


def test_small_formatters():
    assert format_duration(None) == '—' and format_duration(45.4) == '45초' and format_duration(74) == '1분 14초'
    assert short_id('TC-LOGIN-001') == 'TC-LOGIN-001'
    assert short_id('CASE-1a2b3c4d5e6f') == 'CASE-…4d5e6f'


def test_run_csv_has_korean_header_and_duration(workspace):
    from qa_system.workspace import run_list

    text = runs_csv(run_list())
    assert text.startswith('﻿')  # opens correctly in Excel
    rows = list(csv.reader(io.StringIO(text.lstrip('﻿'))))
    assert rows[0][:4] == ['실행 ID', '프로젝트', '대상 URL', '상태']
    assert rows[1][0] == 'r1' and rows[1][3] == '실패' and rows[1][4:7] == ['1', '1', '0']
    assert rows[1][7] == '74.0' and rows[1][8] == '2026-11-17 10:00:00'  # Korea time


def test_quick_run_starts_approved_tests_in_background(workspace):
    pid, rid = workspace
    approved = save_case(pid, rid, dict(template_cases()['page'], engine='web'), reviewed=True)
    save_case(pid, rid, dict(template_cases()['visible'], engine='web'), reviewed=False)
    with patch('qa_system.background.start', return_value='job-1') as start:
        app = app_for('from qa_system.project_ui import dashboard\ndashboard()\n')
        app.button(key=f'launch_{pid}').click().run()
    assert not app.exception
    assert start.call_args.args[:2] == (pid, [approved])  # unapproved tests are left out
    assert app.session_state.project_view == '실행' and app.session_state[f'run_job_{pid}'] == 'job-1'


def test_project_page_header_requirements_and_summary(workspace):
    pid, rid = workspace
    save_case(pid, rid, dict(template_cases()['page'], engine='web'), reviewed=False)
    app = app_for((ROOT / 'streamlit_app.py').read_text(encoding='utf-8'), project_id=pid, project_view='요구사항')
    assert not app.exception
    assert app.button(key='header_run_all').disabled  # nothing approved yet
    assert not app.button(key='header_latest').disabled
    assert any(s.value == 'QA 테스트 요약 및 지표' for s in app.subheader)
    page = ' '.join(m.value for m in app.markdown)
    assert '실행 가능 비율' in page and '0%' in page and '#r1' in page
    assert '빈 이메일' in page and '검토 필요' in page
    app.button(key='header_add_test').click().run()
    assert app.session_state.project_view == '테스트' and app.session_state.case_modal == (pid, rid)


def test_history_filters_by_state_and_offers_csv(workspace):
    app = app_for('from qa_system.project_ui import workspace_history\nworkspace_history()\n')
    assert not app.exception
    assert [b.key for b in app.button if (b.key or '').startswith('recent_')] == ['recent_r1']
    assert next(b for b in app.button if b.key == 'recent_r1').label == '오류 확인'
    app.segmented_control(key='history_status').set_value('통과').run()
    assert not [b for b in app.button if (b.key or '').startswith('recent_')]
    app.button(key='history_reset').click().run()
    assert [b.key for b in app.button if (b.key or '').startswith('recent_')] == ['recent_r1']
    tiles = ' '.join(m.value for m in app.markdown)
    assert '감지된 결함' in tiles and '1건' in tiles and '1분 14초' in tiles
    assert json.loads(storage.rows("SELECT tags FROM projects WHERE name='가입 페이지'")[0]['tags']) == ['가입']
