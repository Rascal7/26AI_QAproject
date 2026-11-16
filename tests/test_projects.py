import json
import sqlite3
import threading
from unittest.mock import patch
import pytest
from werkzeug.serving import make_server
from demo_web.app import create_app
from demo_web.seed import seed
from qa_system import storage, runner
from qa_system.projects import create_project, save_requirement, save_case, requirements, cases, approve_case
from qa_system.web_tests import validate_steps, template_cases


@pytest.fixture
def workspace(tmp_path,monkeypatch):
    path=tmp_path/'qa.db'
    monkeypatch.setattr(storage,'QA_DB',path)
    monkeypatch.setattr(runner,'QA_DB',path)
    storage.initialize()
    return path


def test_old_schema_migration_preserves_existing_records(tmp_path):
    path=tmp_path/'old.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE projects(id INTEGER PRIMARY KEY,name TEXT NOT NULL,target_url TEXT NOT NULL)')
        db.execute('INSERT INTO projects VALUES(1,?,?)',('기존 프로젝트','http://127.0.0.1:5000'))
    storage.initialize(path)
    storage.initialize(path)
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT name,mode FROM projects WHERE id=1').fetchone()==('기존 프로젝트','demo')
        assert db.execute('SELECT COUNT(*) FROM test_cases').fetchone()[0]==10
        assert not db.execute('PRAGMA foreign_key_check').fetchall()


def test_project_requirement_case_isolation(workspace):
    a=create_project('A','https://example.com/a','전체 A','예외 A')
    b=create_project('B','https://example.com/b')
    ra=save_requirement(a,'접속','200 응답','실패 안내')
    rb=save_requirement(b,'접속','페이지 제목 확인')
    definition=dict(template_cases()['page'],engine='web')
    case=save_case(a,ra,definition,reviewed=True)
    assert [r['id'] for r in requirements(a)]==[ra]
    assert [r['id'] for r in requirements(b)]==[rb]
    assert [c['id'] for c in cases(a)]==[case]
    assert cases(b)==[]
    with pytest.raises(ValueError): save_case(b,ra,definition)
    with pytest.raises(ValueError): save_requirement(b,'bad','bad',requirement_id=ra)
    with pytest.raises(ValueError): approve_case(b,case)
    with pytest.raises(ValueError): runner.run_suite([case],project_id=b)


def test_non_demo_cannot_use_db_fixture(workspace):
    from qa_system.catalog import CASES
    p=create_project('외부 페이지','https://example.com/')
    r=save_requirement(p,'로그인','정상 동작')
    with pytest.raises(ValueError): save_case(p,r,dict(CASES['TC-DB-001'],baseline_id='TC-DB-001'))


@pytest.mark.parametrize('steps',[
    [{'action':'navigate','selector':'','value':'https://different.example/'}],
    [{'action':'navigate','selector':'','value':'javascript:alert(1)'},{'action':'assert_status','value':'200'}],
    [{'action':'eval','value':'arbitrary()'}],
    [{'action':'click','selector':'button'}],
    [{'action':'assert_text','selector':'','value':'text'}],
    [{'action':'assert_status','value':'999'}],
])
def test_unsupported_browser_program_is_blocked(steps):
    with pytest.raises(ValueError): validate_steps(steps,'https://example.com/')


def test_ai_receives_project_requirement_and_user_prompt(workspace):
    from qa_system.ai import generate_project_cases, BrowserBatch
    from qa_system.projects import get_project
    pid=create_project('샘플','https://example.com/','전체 정책','공통 오류')
    rid=save_requirement(pid,'제목','제목을 표시한다','제목 없음')
    result=BrowserBatch(cases=[{'description':'제목 표시','expected':'제목이 보인다','review_notes':'선택자 확인 필요',
        'steps':[{'action':'navigate','selector':'','value':''},{'action':'assert_visible','selector':'h1','value':''}]}])
    with patch('qa_system.ai.request_parsed',return_value=result) as request:
        drafts=generate_project_cases(get_project(pid),requirements(pid)[0],'제목이 보이는지 검사해줘')
    payload=request.call_args.args[2]
    assert payload['project']['overview']=='전체 정책'
    assert payload['project']['exceptions']=='공통 오류'
    assert payload['requirement']['id']==rid
    assert payload['user_request']=='제목이 보이는지 검사해줘'
    assert drafts[0]['engine']=='web'
    assert drafts[0]['source']=='ai'


def test_real_web_project_execution_and_history(workspace,tmp_path):
    path=tmp_path/'target.db'; seed(path)
    server=make_server('127.0.0.1',0,create_app(path,testing=True))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        pid=create_project('브라우저 통합 검증',f'http://127.0.0.1:{server.server_port}/login','로그인 UI','오류 안내')
        rid=save_requirement(pid,'로그인 페이지','제목을 보여준다')
        good=save_case(pid,rid,dict(template_cases()['page'],engine='web'),reviewed=True)
        bad=save_case(pid,rid,dict(engine='web',description='의도적 문구 불일치',steps=[
            {'action':'navigate','selector':'','value':''},
            {'action':'assert_text','selector':'h1','value':'존재하지 않는 제목'}]),reviewed=True)
        empty_password=save_case(pid,rid,dict(engine='web',description='빈 비밀번호 안내',steps=[
            {'action':'navigate','selector':'','value':''},
            {'action':'fill','selector':'#email','value':'qa.user@example.com'},
            {'action':'fill','selector':'#password','value':''},
            {'action':'click','selector':'button[type=submit]','value':''},
            {'action':'assert_text','selector':'#password-error','value':'비밀번호를 입력하세요.'}]),reviewed=True)
        literal_password=save_case(pid,rid,dict(engine='web',description='비밀번호 원문 입력 차단',steps=[
            {'action':'navigate','selector':'','value':''},
            {'action':'fill','selector':'#password','value':'plain-text'},
            {'action':'assert_visible','selector':'h1','value':''}]),reviewed=True)
        run_id=runner.run_suite([good,bad,empty_password,literal_password],project_id=pid)
        run=storage.rows('SELECT * FROM test_runs WHERE run_id=?',(run_id,))[0]
        assert run['project_id']==pid
        assert run['target_url'].endswith('/login')
        results=storage.rows('SELECT outcome,details FROM test_results WHERE run_id=? ORDER BY id',(run_id,))
        assert [r['outcome'] for r in results]==['PASS','FAIL','PASS','ERROR'],results
        assert '${QA_TEST_PASSWORD}' in json.loads(results[3]['details'])['error']
        assert json.loads(results[0]['details'])['expected']['requirement_id']==rid
        report=storage.rows('SELECT markdown FROM reports WHERE run_id=?',(run_id,))[0]['markdown']
        assert '브라우저 통합 검증' in report and '로그인 UI' in report
        assert '전체 예외사항: 오류 안내' in report
        assert len(storage.rows('SELECT id FROM bug_reports'))==1
        assert not storage.rows('SELECT run_id FROM test_runs WHERE project_id=1')
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
