import json
import threading
from unittest.mock import patch
import pytest
from flask import Flask
from streamlit.testing.v1 import AppTest
from werkzeug.serving import make_server
from demo_web.app import create_app
from demo_web.seed import seed
from qa_system import storage
from qa_system.page_context import PageContextError, capture, check_selectors, summarize_check
from qa_system.projects import create_project, save_requirement, requirements, get_project


@pytest.fixture
def serve():
    servers = []

    def start(app):
        server = make_server('127.0.0.1', 0, app)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return f'http://127.0.0.1:{server.server_port}'
    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


def test_capture_reads_login_structure_and_checks_selectors(tmp_path, serve):
    seed(tmp_path / 'demo.db')
    url = serve(create_app(tmp_path / 'demo.db', testing=True)) + '/login'
    context = capture(url)
    assert context['status'] == 200 and context['title'] == 'QA 데모 로그인'
    by_selector = {e['selector']: e for e in context['elements']}
    for testid in ('email-input', 'password-input', 'login-submit', 'login-error', 'email-error'):
        assert by_selector[f'[data-testid="{testid}"]']['unique'] is True
    assert by_selector['[data-testid="password-input"]']['type'] == 'password'
    assert by_selector['[data-testid="email-error"]']['initially_empty'] is True
    counts = check_selectors(url, ['[data-testid="email-input"]', 'label', '#missing', 'button[['])
    assert counts == {'[data-testid="email-input"]': 1, 'label': 2, '#missing': 0, 'button[[': 'invalid'}


def test_capture_never_reads_field_values(serve):
    app = Flask(__name__)
    app.get('/')(lambda: '<h1>폼</h1><input id="a" value="TypedSecret1"><textarea id="b">TypedSecret2</textarea>'
                         '<select id="c"><option selected>TypedSecret3</option></select>')
    context = capture(serve(app) + '/')
    assert {'#a', '#b', '#c'} <= {e['selector'] for e in context['elements']}
    assert 'TypedSecret1' not in json.dumps(context) and 'TypedSecret2' not in json.dumps(context)


def test_unreachable_page_gives_readable_error():
    with pytest.raises(PageContextError, match='접속할 수 없습니다'):
        capture('http://127.0.0.1:9/')


def test_summary_separates_missing_multiple_and_invalid():
    steps = [{'action': 'navigate', 'selector': '', 'value': ''},
             {'action': 'fill', 'selector': '#email', 'value': 'a@b.c'},
             {'action': 'click', 'selector': 'button', 'value': ''},
             {'action': 'assert_text', 'selector': '#after-login', 'value': '환영'},
             {'action': 'assert_visible', 'selector': 'a[[', 'value': ''}]
    summary = summarize_check(steps, {'#email': 1, 'button': 3, '#after-login': 0, 'a[[': 'invalid'})
    assert summary == {'selectors': ['#email', 'button', '#after-login', 'a[['], 'total': 4, 'unique': 1,
                       'multiple': ['button'], 'missing': ['#after-login'], 'invalid': ['a[[']}


def test_ai_prompt_includes_page_structure_only_when_available(tmp_path, monkeypatch):
    from qa_system.ai import BrowserBatch, generate_project_cases
    monkeypatch.setattr(storage, 'QA_DB', tmp_path / 'qa.db')
    pid = create_project('샘플', 'https://example.com/')
    save_requirement(pid, '제목', '제목을 표시한다')
    result = BrowserBatch(cases=[{'description': '제목', 'expected': '보임', 'review_notes': '',
        'steps': [{'action': 'navigate', 'selector': '', 'value': ''}, {'action': 'assert_visible', 'selector': 'h1', 'value': ''}]}])
    context = {'title': '샘플', 'elements': [{'tag': 'h1', 'selector': 'h1', 'unique': True, 'text': '샘플'}]}
    with patch('qa_system.ai.request_parsed', return_value=result) as request:
        with_page = generate_project_cases(get_project(pid), requirements(pid)[0], '제목 확인', context)
        without = generate_project_cases(get_project(pid), requirements(pid)[0], '제목 확인')
    (_, rules, payload), (_, rules_without, payload_without) = (c.args for c in request.call_args_list)
    assert payload['page_context'] == context and 'page_context' not in payload_without
    assert 'selector 값을' in rules and '추정했음을' in rules_without
    assert with_page[0]['page_context_used'] is True and without[0]['page_context_used'] is False


def _dialog_app(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'QA_DB', tmp_path / 'qa.db')
    pid = create_project('웹 검사', 'https://example.com')
    rid = save_requirement(pid, '로그인', '오류 문구를 보여준다')
    app = AppTest.from_string(
        'from qa_system.project_ui import tests_page\n'
        'from qa_system.projects import get_project\n'
        f'tests_page(get_project({pid}))\n', default_timeout=15)
    app.session_state[f'req_filter_{pid}'] = rid
    app.run()
    app.button(key='show_test_modal').click().run()
    app.text_area(key=f'prompt_{pid}_{rid}').input('빈 이메일 오류 확인').run()
    return app


DRAFT = dict(engine='web', source='ai', description='빈 이메일', expected='오류 문구', review_notes='',
             steps=[dict(action='navigate', selector='', value=''), dict(action='click', selector='#submit', value=''),
                    dict(action='assert_text', selector='#email-error', value='이메일을 입력하세요.')])


def test_dialog_checks_generated_selectors_on_the_page(tmp_path, monkeypatch):
    app = _dialog_app(tmp_path, monkeypatch)
    context = {'elements': [{'selector': '#submit'}, {'selector': '#email-error'}]}
    with patch('qa_system.project_ui.capture', return_value=context), \
         patch('qa_system.project_ui.generate_project_cases', return_value=[dict(DRAFT)]) as generate, \
         patch('qa_system.project_ui.check_selectors', return_value={'#submit': 1, '#email-error': 1}):
        next(b for b in app.button if b.label == '✦ 테스트 생성').click().run()
    assert not app.exception
    assert generate.call_args.args[3] is context
    assert any('요소 2개' in c.value for c in app.caption)
    assert any('2개 중 2개' in s.value for s in app.success)


def test_dialog_falls_back_when_page_cannot_be_read(tmp_path, monkeypatch):
    app = _dialog_app(tmp_path, monkeypatch)
    with patch('qa_system.project_ui.capture', side_effect=PageContextError('페이지에 접속할 수 없습니다')), \
         patch('qa_system.project_ui.generate_project_cases', return_value=[dict(DRAFT)]) as generate:
        next(b for b in app.button if b.label == '✦ 테스트 생성').click().run()
    assert not app.exception
    assert generate.call_args.args[3] is None
    assert any('페이지 구조 없이 생성했습니다' in w.value for w in app.warning)
