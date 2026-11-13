import pytest
from streamlit.testing.v1 import AppTest
from qa_system import storage
from qa_system.projects import cases, create_project, save_requirement


@pytest.mark.parametrize('kind', ['demo', 'web', 'ai'])
def test_registration_refreshes_list_immediately(tmp_path, monkeypatch, kind):
    monkeypatch.setattr(storage, 'QA_DB', tmp_path / 'qa.db')
    storage.initialize()
    pid = 1 if kind == 'demo' else create_project('웹 검사', 'https://example.com')
    rid = save_requirement(pid, '접속 확인', '페이지는 정상 응답한다.')
    app = AppTest.from_string(
        'from qa_system.project_ui import tests_page\n'
        'from qa_system.projects import get_project\n'
        f'tests_page(get_project({pid}))\n', default_timeout=15)
    app.session_state[f'req_filter_{pid}'] = rid
    if kind == 'ai':
        app.session_state[f'drafts_{pid}_{rid}'] = [dict(
            engine='web', source='ai', description='AI 접속 확인', expected='HTTP 200',
            steps=[dict(action='navigate', value=''), dict(action='assert_status', value='200')])]
    app.run()
    assert not app.exception
    app.button(key='show_test_modal').click().run()
    if kind == 'demo':
        app.multiselect[0].select(app.multiselect[0].options[0]).run()
        label = '선택한 테스트 추가'
    elif kind == 'ai':
        app.checkbox[0].check().run()
        label = '프로젝트에 추가'
    else:
        label = '테스트 추가'
    next(b for b in app.button if b.label == label).click().run()
    assert not app.exception
    saved = cases(pid, rid)
    assert len(saved) == 1
    assert any(saved[0]['description'] in exp.label for exp in app.expander)
    assert app.success
    app.run()
    assert len(cases(pid, rid)) == 1
    if kind == 'ai':
        app.button(key='show_test_modal').click().run()
        assert next(b for b in app.button if b.label == '등록 완료').disabled
