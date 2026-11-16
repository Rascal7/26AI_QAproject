import json
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from demo_web.db import ROOT
from qa_system import storage, runner
from qa_system.catalog import CASES
from qa_system.projects import create_project, delete_project, get_project, cases


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    path = tmp_path / 'qa.db'
    monkeypatch.setattr(storage, 'QA_DB', path)
    monkeypatch.setattr(runner, 'QA_DB', path)
    storage.initialize()
    return path


def test_queries_do_not_rerun_schema_setup(workspace, monkeypatch):
    calls = []
    monkeypatch.setattr(storage, 'initialize', lambda *a: calls.append(a))
    for _ in range(5):
        storage.rows('SELECT 1')
    assert calls == []


def test_deleted_demo_gives_clear_error_and_restores_without_taking_other_ids(workspace):
    delete_project(1)
    # The projects table is now empty, so SQLite hands id 1 to the next project.
    web = create_project('다른 웹 프로젝트', 'https://example.com')
    assert web == 1
    with pytest.raises(ValueError, match='--restore-demo'):
        runner.run_suite()
    restored = storage.restore_demo()
    assert restored != web
    assert get_project(web)['mode'] == 'web'
    assert get_project(restored)['mode'] == 'demo'
    assert sorted(c['id'] for c in cases(restored)) == sorted(CASES)
    assert storage.baseline_project_id() == restored
    assert storage.restore_demo() == restored


def test_stale_running_run_is_closed_and_no_longer_blocks_deletion(workspace):
    old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    fresh = datetime.now(timezone.utc).isoformat()
    snapshots = json.dumps({'cases': [{}, {}]})
    with sqlite3.connect(workspace) as db:
        db.execute("INSERT INTO test_runs(run_id,project_id,started_at,status,snapshots) VALUES('stale',1,?,'RUNNING',?)", (old, snapshots))
        db.execute("INSERT INTO test_runs(run_id,project_id,started_at,status,snapshots) VALUES('active',1,?,'RUNNING',?)", (fresh, snapshots))
    assert storage.recover_stale_runs() == ['stale']
    states = {r['run_id']: r['status'] for r in storage.rows('SELECT run_id,status FROM test_runs')}
    assert states == {'stale': 'ERROR', 'active': 'RUNNING'}
    with pytest.raises(ValueError, match='실행 중'):
        delete_project(1)
    with sqlite3.connect(workspace) as db:
        db.execute("UPDATE test_runs SET started_at=? WHERE run_id='active'", (old,))
    delete_project(1)
    assert storage.rows('SELECT * FROM test_runs') == []


def fake_pytest(output, results=0):
    """Popen stand-in: writes output to the log and finishes one result file per poll."""
    def start(command, stdout, **kwargs):
        out = Path(command[command.index('--result-dir') + 1])
        stdout.write(output.encode('utf-8'))
        stdout.flush()
        state = {'written': 0}

        def poll():
            if state['written'] < results:
                (out / f"test_case_{state['written']}.json").write_text(json.dumps(
                    {'setup_status': 'ready', 'outcome': 'PASS', 'http': [], 'observations': []}), encoding='utf-8')
                state['written'] += 1
                return None
            return 0
        return MagicMock(returncode=0 if results else 1, poll=poll, pid=0)
    return start


def test_progress_is_reported_per_finished_test_and_raw_log_removed(workspace, monkeypatch):
    monkeypatch.setattr(runner.subprocess, 'Popen', fake_pytest('3 passed', results=3))
    monkeypatch.setattr(runner.time, 'sleep', lambda s: None)
    seen = []
    run_id = runner.run_suite(['TC-LOGIN-001', 'TC-LOGIN-002', 'TC-LOGIN-003'], progress=lambda d, t: seen.append((d, t)))
    try:
        assert seen[0] == (0, 3) and seen[-1] == (3, 3) and seen == sorted(seen)
        outcomes = [r['outcome'] for r in storage.rows('SELECT outcome FROM test_results WHERE run_id=?', (run_id,))]
        assert outcomes == ['PASS', 'PASS', 'PASS']
        assert (ROOT / 'artifacts' / run_id / 'pytest.log').read_text(encoding='utf-8') == '3 passed'
        assert not (ROOT / 'artifacts' / run_id / 'pytest.raw.log').exists()
    finally:
        shutil.rmtree(ROOT / 'artifacts' / run_id, ignore_errors=True)


def test_every_test_needs_db_approval_and_old_ai_demo_tests_run_fixed_code(workspace, monkeypatch):
    from qa_system.projects import save_case, approve_case
    case = dict(CASES['TC-DB-001'], baseline_id='TC-DB-001', engine='demo', source='ai', description='초기 AI 테스트')
    case_id = save_case(1, CASES['TC-DB-001']['requirement_id'], case, reviewed=False)
    with pytest.raises(ValueError, match='검토하고 승인'):
        runner.run_suite([case_id])
    approve_case(1, case_id)
    monkeypatch.setattr(runner.subprocess, 'Popen', fake_pytest('', results=1))
    monkeypatch.setattr(runner.time, 'sleep', lambda s: None)
    run_id = runner.run_suite([case_id])
    try:
        code = (ROOT / 'artifacts' / run_id / 'test_selected.py').read_text(encoding='utf-8')
        assert code == "from qa_system.contracts import execute_case\n\ndef test_case_0(qa_env):\n    execute_case(qa_env, 'TC-DB-001')\n"
    finally:
        shutil.rmtree(ROOT / 'artifacts' / run_id, ignore_errors=True)


def test_missing_browser_is_reported_with_install_command(workspace, monkeypatch):
    monkeypatch.setattr(runner.subprocess, 'Popen',
                        fake_pytest("BrowserType.launch: Executable doesn't exist at C:\\ms-playwright\\chrome.exe"))
    run_id = runner.run_suite(['TC-LOGIN-001'])
    try:
        result = storage.rows('SELECT outcome,details FROM test_results WHERE run_id=?', (run_id,))[0]
        assert result['outcome'] == 'ERROR'
        assert json.loads(result['details'])['error'] == runner.BROWSER_MISSING
        report = storage.rows('SELECT markdown FROM reports WHERE run_id=?', (run_id,))[0]['markdown']
        assert '실행 완료율: 0/1' in report and '유효 테스트 비율' not in report
    finally:
        shutil.rmtree(ROOT / 'artifacts' / run_id, ignore_errors=True)
