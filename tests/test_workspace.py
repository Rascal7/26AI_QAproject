from datetime import date
import json
import pytest
from streamlit.testing.v1 import AppTest
from demo_web.db import connect
from qa_system import storage
from qa_system.projects import create_project, get_project, save_project
from qa_system.workspace import project_list, run_list, all_tags


@pytest.fixture
def populated(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'QA_DB', tmp_path/'qa.db')
    storage.initialize()
    ids=[create_project(f'Project {i}', 'https://example.com', tags='DB, #DB, 로그인' if i==0 else '웹') for i in range(6)]
    with connect(storage.QA_DB) as db:
        for i,pid in enumerate(reversed(ids)):
            db.execute('INSERT INTO test_runs VALUES(?,?,?,?,?,?,?,?,?,?)',
                (f'run{i}',pid,'https://example.com','normal','1','2026-11-04T'+f'{15+i:02}:00:00+00:00',None,'COMPLETED','{}',''))
    return ids


def test_workspace_sort_tags_and_korean_dates(populated):
    assert [p['id'] for p in project_list()[:6]] == populated
    assert [p['id'] for p in project_list(tags=['DB'])] == populated[:1]
    assert all_tags()==['DB','로그인','웹']
    assert len(run_list(start=date(2026,11,5),end=date(2026,11,5)))==6
    assert run_list(end=date(2026,11,4))==[]
    assert len(run_list(tags=['DB']))==1
    p=get_project(populated[0])
    save_project(p['id'],p['name'],'updated','')
    assert json.loads(get_project(p['id'])['tags'])==['DB','로그인']
    save_project(p['id'],p['name'],'','',tags='')
    assert run_list(tags=['DB'])==[]


def test_home_limits_and_more_navigation(populated):
    app=AppTest.from_string('''
import streamlit as st
from qa_system.project_ui import dashboard, workspace_history
if st.session_state.get('workspace_view')=='실행 기록':
    workspace_history()
else:
    dashboard(collection=st.session_state.get('workspace_view')=='프로젝트')
''',default_timeout=15).run()
    assert not app.exception
    assert len([b for b in app.button if (b.key or '').startswith('open_')])==4
    assert len([b for b in app.button if (b.key or '').startswith('recent_')])==5
    app.button(key='more_projects').click().run()
    assert not app.exception
    assert len([b for b in app.button if (b.key or '').startswith('open_')])==7
    app.multiselect[0].select('DB').run()
    assert len([b for b in app.button if (b.key or '').startswith('open_')])==1
    app.session_state.workspace_view='홈'
    app.run()
    app.button(key='more_runs').click().run()
    assert len([b for b in app.button if (b.key or '').startswith('recent_')])==6
    app.multiselect[0].select('DB').run()
    assert len([b for b in app.button if (b.key or '').startswith('recent_')])==1
    app.button(key='recent_run5').click().run()
    assert app.session_state.project_id==populated[0]
    assert app.session_state[f'selected_run_{populated[0]}']=='run5'

