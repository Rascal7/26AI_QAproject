"""Open the existing QA server, or start it and open it when ready."""

import argparse
import importlib.util
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
URL = 'http://127.0.0.1:8501'


def healthy():
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(URL + '/_stcore/health', timeout=2) as response:
            return response.status == 200 and response.read(32).strip() == b'ok'
    except (OSError, urllib.error.URLError):
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='Check without launching a browser or server')
    args = parser.parse_args()
    if healthy():
        print('QA server is already running: ' + URL, flush=True)
        if not args.check:
            webbrowser.open(URL)
        return 0
    if args.check:
        print('QA server is not responding: ' + URL)
        return 1
    if importlib.util.find_spec('streamlit') is None:
        print('Streamlit is missing. Install requirements.txt using the project virtual environment.')
        return 1
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1', 8501)) == 0:
            print(
                'Port 8501 is occupied, but the QA server is not ready. Retry shortly or close the application using this port.'
            )
            return 1
    print('Starting QA. Keep this window open while using the app.\n' + URL, flush=True)
    process = subprocess.Popen(
        [
            sys.executable,
            '-m',
            'streamlit',
            'run',
            str(ROOT / 'streamlit_app.py'),
            '--server.address',
            '127.0.0.1',
            '--server.port',
            '8501',
            '--server.headless',
            'true',
            '--browser.gatherUsageStats',
            'false',
        ],
        cwd=ROOT,
    )
    try:
        for _ in range(60):
            if process.poll() is not None:
                return process.returncode or 1
            if healthy():
                webbrowser.open(URL)
                return process.wait()
            time.sleep(0.5)
        print(
            'Startup is taking longer than expected. See the server messages above; open ' + URL + ' when ready.',
            flush=True,
        )
        return process.wait()
    except KeyboardInterrupt:
        process.terminate()
        process.wait()
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
