import sqlite3
import pytest
from qa_system import storage
from qa_system.projects import create_project, delete_project, get_project


def test_delete_removes_owned_history_and_does_not_reseed(tmp_path, monkeypatch):
    path = tmp_path / 'qa.db'
    monkeypatch.setattr(storage, 'QA_DB', path)
    storage.initialize()
    other = create_project('유지할 프로젝트', 'https://example.com')
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO test_runs(run_id,project_id,status) VALUES('old',1,'COMPLETED')")
        db.execute("INSERT INTO test_results(id,run_id,case_id,outcome) VALUES(1,'old','TC-LOGIN-001','FAIL')")
        db.execute("INSERT INTO bug_reports(result_id,title) VALUES(1,'오류')")
        db.execute("INSERT INTO reports(run_id,markdown) VALUES('old','보고서')")
    delete_project(1)
    storage.initialize()
    assert get_project(other)['name'] == '유지할 프로젝트'
    with pytest.raises(ValueError):
        get_project(1)
    with sqlite3.connect(path) as db:
        for table in ('requirements', 'test_cases', 'test_runs', 'test_results', 'bug_reports', 'reports'):
            assert db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] == 0
        assert not db.execute('PRAGMA foreign_key_check').fetchall()


def test_running_project_cannot_be_deleted(tmp_path, monkeypatch):
    path = tmp_path / 'qa.db'
    monkeypatch.setattr(storage, 'QA_DB', path)
    storage.initialize()
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO test_runs(run_id,project_id,status) VALUES('active',1,'RUNNING')")
    with pytest.raises(ValueError, match='실행 중'):
        delete_project(1)
    assert get_project(1)
    assert len(storage.rows('SELECT * FROM test_cases')) == 10


def test_delete_dialog_requires_confirmation(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setattr(storage, 'QA_DB', tmp_path / 'qa.db')
    storage.initialize()
    from demo_web.db import ROOT

    app = AppTest.from_file(str(ROOT / 'streamlit_app.py'), default_timeout=15)
    app.session_state.project_id = 1
    app.session_state.project_view = '프로젝트 설정'
    app.run()
    app.button(key='delete_project').click().run()
    assert get_project(1)
    app.button(key='cancel_delete_project').click().run()
    assert get_project(1)
    app.button(key='delete_project').click().run()
    app.button(key='confirm_delete_project').click().run()
    assert not app.exception
    assert app.session_state.project_id is None
    assert app.session_state.workspace_view == '프로젝트'
    assert storage.rows('SELECT * FROM projects') == []
