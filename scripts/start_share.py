"""Share WebQA through a public ngrok link for a live demo.

Starts the login demo (5000) and the QA app (8501, shared mode) on this computer, opens an ngrok
tunnel to the QA app and prints the link. Visitors need the access code (QA_ACCESS_CODE in .env,
created on first use). Press Ctrl+C to stop everything.
"""

import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

from dotenv import load_dotenv, set_key

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / '.env'
LOG = ROOT / 'artifacts' / 'ngrok.log'
DEMO_PORT = 5000


def port_open(port):
    with socket.socket() as probe:
        probe.settimeout(0.5)
        return probe.connect_ex(('127.0.0.1', port)) == 0


def healthy(url):
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url, timeout=2) as response:
            return response.status == 200
    except OSError:
        return False


def wait_until(check, seconds, processes):
    for _ in range(int(seconds * 2)):
        if check():
            return True
        if any(p.poll() is not None for p in processes):
            return False
        time.sleep(0.5)
    return False


def tunnel_url():
    """Read the public https URL from ngrok's JSON log."""
    if not LOG.exists():
        return None
    for line in LOG.read_text(encoding='utf-8', errors='replace').splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get('msg') == 'started tunnel' and str(entry.get('url', '')).startswith('https://'):
            return entry['url']
        if entry.get('lvl') in ('eror', 'crit') and entry.get('err'):
            raise RuntimeError(str(entry['err']).splitlines()[0])
    return None


def access_code():
    code = os.getenv('QA_ACCESS_CODE', '').strip()
    if code:
        return code
    code = secrets.token_urlsafe(6)
    ENV.touch(exist_ok=True)
    set_key(str(ENV), 'QA_ACCESS_CODE', code, quote_mode='never')
    print('접속 코드를 새로 만들어 .env의 QA_ACCESS_CODE에 저장했습니다.')
    return code


def stop(processes):
    for process in reversed(processes):
        if process.poll() is None:
            process.terminate()
    for process in processes:
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8501, help='QA app port (default 8501)')
    QA_PORT = parser.parse_args().port
    load_dotenv(ENV)
    ngrok = shutil.which('ngrok')
    if not ngrok:
        print('ngrok이 없습니다. https://ngrok.com 에서 설치하고 `ngrok config add-authtoken <토큰>`을 실행하세요.')
        return 1
    if port_open(QA_PORT):
        print(f'{QA_PORT} 포트를 이미 쓰고 있습니다. start_qa.cmd 창 등 기존 QA 앱을 닫고 다시 실행하세요.')
        return 1
    code = access_code()
    processes = []
    try:
        if port_open(DEMO_PORT):
            print(f'로그인 데모가 이미 켜져 있어 그대로 사용합니다 (http://127.0.0.1:{DEMO_PORT}).')
        else:
            processes.append(subprocess.Popen([sys.executable, '-m', 'demo_web.app'], cwd=ROOT))
        shared_env = {**os.environ, 'QA_SHARED': '1', 'QA_ACCESS_CODE': code}
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    '-m',
                    'streamlit',
                    'run',
                    str(ROOT / 'streamlit_app.py'),
                    '--server.address',
                    '127.0.0.1',
                    '--server.port',
                    str(QA_PORT),
                    '--server.headless',
                    'true',
                    '--browser.gatherUsageStats',
                    'false',
                ],
                cwd=ROOT,
                env=shared_env,
            )
        )
        print('QA 앱을 시작하는 중입니다...', flush=True)
        if not wait_until(lambda: healthy(f'http://127.0.0.1:{QA_PORT}/_stcore/health'), 60, processes):
            print('QA 앱이 시작되지 않았습니다. 위 메시지를 확인하세요.')
            return 1
        LOG.parent.mkdir(exist_ok=True)
        LOG.unlink(missing_ok=True)
        command = [ngrok, 'http', str(QA_PORT), '--log', str(LOG), '--log-format', 'json']
        if os.getenv('QA_SHARE_DOMAIN'):
            command += ['--url', os.environ['QA_SHARE_DOMAIN']]
        processes.append(subprocess.Popen(command, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        url = None
        try:
            for _ in range(60):
                url = tunnel_url()
                if url or processes[-1].poll() is not None:
                    break
                time.sleep(0.5)
        except RuntimeError as error:
            print('ngrok 오류: ' + str(error))
            return 1
        if not url:
            print(f'ngrok 링크를 받지 못했습니다. {LOG} 를 확인하세요.')
            return 1
        print(
            '\n'
            '=============================================\n'
            f'  공유 링크 : {url}\n'
            f'  접속 코드 : {code}\n'
            '=============================================\n'
            '처음 접속하면 ngrok 안내 화면이 나옵니다. "Visit Site"를 누르면 WebQA가 열립니다.\n'
            '이 창을 닫거나 Ctrl+C를 누르면 공유가 끝납니다.',
            flush=True,
        )
        while all(p.poll() is None for p in processes):
            time.sleep(1)
        print('서버 하나가 종료되어 공유를 끝냅니다.')
        return 1
    except KeyboardInterrupt:
        print('공유를 끝냅니다.')
        return 0
    finally:
        stop(processes)


if __name__ == '__main__':
    raise SystemExit(main())
