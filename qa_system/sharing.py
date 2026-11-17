"""Shared mode: the app is reachable through a public link (scripts/start_share.py sets QA_SHARED=1).

Visitors must enter the access code first, and the server's browser is kept off this computer and its
private network, except for the bundled login demo.
"""

import hmac
import ipaddress
import os
import socket
from urllib.parse import urlsplit

from qa_system.catalog import TARGET

BLOCKED = (
    '공유 링크로 실행 중에는 이 컴퓨터나 내부망 주소를 쓸 수 없습니다. '
    '기본 로그인 데모(http://127.0.0.1:5000)와 인터넷 주소만 사용할 수 있습니다.'
)


def shared():
    return os.getenv('QA_SHARED') == '1'


def access_code():
    return os.getenv('QA_ACCESS_CODE', '').strip()


def code_matches(entered):
    code = access_code()
    return bool(code) and hmac.compare_digest(entered.strip().encode(), code.encode())


def _origin(url):
    parts = urlsplit(url)
    return parts.scheme, (parts.hostname or '').lower(), parts.port or (443 if parts.scheme == 'https' else 80)


def check_target(url):
    """In shared mode, raise ValueError unless url is the login demo or resolves only to public addresses."""
    if not shared():
        return
    scheme, host, port = _origin(url)
    demo = _origin(TARGET)
    if (scheme, port) == demo[::2] and host in (demo[1], 'localhost'):
        return
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError):
        raise ValueError('주소를 찾을 수 없습니다. 웹 주소를 확인하세요.')
    for info in infos:
        if not ipaddress.ip_address(info[4][0].split('%')[0]).is_global:
            raise ValueError(BLOCKED)
