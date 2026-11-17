import socket
import pytest
from streamlit.testing.v1 import AppTest
from demo_web.db import ROOT
from qa_system import page_context, sharing, storage
from qa_system.projects import create_project


def resolves_to(monkeypatch, address):
    monkeypatch.setattr(
        socket, 'getaddrinfo', lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (address, 0))]
    )


def test_local_use_is_unrestricted(monkeypatch):
    monkeypatch.delenv('QA_SHARED', raising=False)
    sharing.check_target('http://127.0.0.1:8501')
    sharing.check_target('http://192.168.0.1/admin')


@pytest.mark.parametrize('url', ['http://127.0.0.1:8501', 'http://localhost:9000', 'http://192.168.0.1/admin'])
def test_shared_mode_blocks_this_computer_and_private_network(monkeypatch, url):
    monkeypatch.setenv('QA_SHARED', '1')
    with pytest.raises(ValueError, match='내부망'):
        sharing.check_target(url)


def test_shared_mode_allows_login_demo_and_public_sites(monkeypatch):
    monkeypatch.setenv('QA_SHARED', '1')
    sharing.check_target('http://127.0.0.1:5000/login')
    sharing.check_target('http://localhost:5000/home')
    resolves_to(monkeypatch, '93.184.215.14')
    sharing.check_target('https://example.com/signup')
    resolves_to(monkeypatch, '10.0.0.7')  # a public name pointing inside is still blocked
    with pytest.raises(ValueError):
        sharing.check_target('https://intranet.example.com')


def test_shared_mode_guards_registration_and_page_reading(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'QA_DB', tmp_path / 'qa.db')
    monkeypatch.setenv('QA_SHARED', '1')
    with pytest.raises(ValueError, match='내부망'):
        create_project('공유기', 'http://192.168.0.1')
    with pytest.raises(page_context.PageContextError, match='내부망'):
        page_context.capture('http://127.0.0.1:8501')


def test_code_matches_only_the_configured_code(monkeypatch):
    monkeypatch.setenv('QA_ACCESS_CODE', 'open-sesame')
    assert sharing.code_matches(' open-sesame ') and not sharing.code_matches('open')
    monkeypatch.setenv('QA_ACCESS_CODE', '')
    assert not sharing.code_matches('')


def test_shared_app_asks_for_access_code_first(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'QA_DB', tmp_path / 'qa.db')
    monkeypatch.setenv('QA_SHARED', '1')
    monkeypatch.setenv('QA_ACCESS_CODE', 'open-sesame')
    app = AppTest.from_string((ROOT / 'streamlit_app.py').read_text(encoding='utf-8'), default_timeout=15).run()
    assert not app.exception
    assert not [b for b in app.button if b.label == '대시보드']  # nothing behind the gate is shown
    app.text_input[0].input('wrong')
    next(b for b in app.button if b.label == '입장').click().run()
    assert app.error and 'access_granted' not in app.session_state
    app.text_input[0].input('open-sesame')
    next(b for b in app.button if b.label == '입장').click().run()
    assert not app.exception
    assert app.session_state.access_granted
    assert [b for b in app.button if b.label == '대시보드']
