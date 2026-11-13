from unittest.mock import MagicMock
from scripts import start_qa


def test_existing_server_opens_without_starting_another(monkeypatch):
    monkeypatch.setattr('sys.argv', ['start_qa.py'])
    monkeypatch.setattr(start_qa, 'healthy', lambda: True)
    browser = MagicMock()
    launch = MagicMock()
    monkeypatch.setattr(start_qa.webbrowser, 'open', browser)
    monkeypatch.setattr(start_qa.subprocess, 'Popen', launch)
    assert start_qa.main() == 0
    browser.assert_called_once_with(start_qa.URL)
    launch.assert_not_called()


def test_new_server_opens_after_health_check(monkeypatch):
    monkeypatch.setattr('sys.argv', ['start_qa.py'])
    health = iter([False, True])
    monkeypatch.setattr(start_qa, 'healthy', lambda: next(health))
    socket = MagicMock()
    socket.__enter__.return_value.connect_ex.return_value = 1
    monkeypatch.setattr(start_qa.socket, 'socket', lambda: socket)
    process = MagicMock()
    process.poll.return_value = None
    process.wait.return_value = 0
    launch = MagicMock(return_value=process)
    browser = MagicMock()
    monkeypatch.setattr(start_qa.subprocess, 'Popen', launch)
    monkeypatch.setattr(start_qa.webbrowser, 'open', browser)
    assert start_qa.main() == 0
    launch.assert_called_once()
    browser.assert_called_once_with(start_qa.URL)
