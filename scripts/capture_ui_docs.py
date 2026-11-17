"""Capture the current QA app screens for docs/images from a disposable workspace.

Prepares real data first: the 10 baseline login tests, the intentional-fault tests with AI failure
analysis, and one AI test generation that reads the page structure. Then screenshots four screens:
dashboard, project requirements, AI test generation, and failure analysis.

Usage:  .venv\\Scripts\\python.exe -m scripts.capture_ui_docs
Needs port 5000 (login demo) and 8505 free. Makes about 4 OpenAI calls. data/qa.db is never touched.
Set QA_BROWSER_CHANNEL=msedge when Playwright's Chromium is not installed.
"""

import os
import re
import socket
import subprocess
import sys
import tempfile
import uuid
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Folder name only; it is created when the script runs, so importing this module leaves nothing behind.
WORK = Path(tempfile.gettempdir()) / f'ui-docs-{uuid.uuid4().hex[:8]}'
os.environ['QA_DB_PATH'] = str(WORK / 'qa.db')

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / '.env')

from werkzeug.serving import make_server  # noqa: E402
from demo_web.app import create_app  # noqa: E402
from demo_web.seed import seed  # noqa: E402
from qa_system import failure_analysis, storage  # noqa: E402
from qa_system.projects import cases, get_project, save_project  # noqa: E402
from qa_system.runner import run_suite  # noqa: E402
from scripts.setup_fault_projects import install  # noqa: E402

OUT = ROOT / 'docs/images'
APP_PORT = 8505
AI_REQUEST = '이메일을 비운 채 로그인하면 이메일 오류 문구가 보이는지 확인하는 테스트를 만들어줘.'


def port_free(port):
    with socket.socket() as probe:
        return probe.connect_ex(('127.0.0.1', port)) != 0


def prepare():
    storage.initialize()
    demo = storage.baseline_project_id()
    project = get_project(demo)
    # Requirement text states the exact messages, as a real specification would.
    save_project(
        demo,
        project['name'],
        project['overview'] or '이메일과 비밀번호로 로그인하고, 계정 상태에 따라 접근을 제어한다.',
        project['exceptions']
        or '빈 이메일은 "이메일을 입력하세요.", 빈 비밀번호는 "비밀번호를 입력하세요."를 입력창 아래에 '
        '표시하고 요청을 보내지 않는다. 틀린 비밀번호는 "이메일 또는 비밀번호가 올바르지 않습니다.", 비활성·잠긴 계정은 '
        '"현재 로그인할 수 없는 계정입니다."를 표시한다.',
        tags=['로그인', 'DB', '회귀 테스트'],
    )
    print('baseline run', run_suite(), flush=True)
    installed = install()
    for project_id, case_ids in installed.items():
        faults = [c['id'] for c in cases(project_id) if c['id'] in case_ids]
        run_id = run_suite(faults, project_id=project_id)
        print('fault run', run_id, flush=True)
        if project_id == demo:
            print('analysis', failure_analysis.analyze_run(run_id), flush=True)
    return demo


def wait_for(url, seconds=60):
    for _ in range(seconds * 2):
        try:
            with urllib.request.urlopen(url, timeout=2):
                return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError(f'{url} did not start')


def capture(demo):
    from playwright.sync_api import expect, sync_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=os.getenv('QA_BROWSER_CHANNEL') or None)
        page = browser.new_page(viewport={'width': 1440, 'height': 1000}, device_scale_factor=1)
        page.goto(f'http://127.0.0.1:{APP_PORT}')
        expect(page.get_by_role('heading', name='QA 워크스페이스', exact=True)).to_be_visible(timeout=60000)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT / 'dashboard.png'))

        page.locator(f'.st-key-open_{demo} button').click()
        expect(page.get_by_role('heading', name='QA 테스트 요약 및 지표')).to_be_visible(timeout=30000)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT / 'requirements.png'))

        nav = page.locator('.st-key-project_nav')
        nav.get_by_role('button', name='테스트 추가', exact=True).click()
        page.locator('.st-key-show_test_modal button').click()
        dialog = page.get_by_role('dialog')
        expect(dialog.get_by_role('heading', name='AI 테스트 생성')).to_be_visible(timeout=30000)
        dialog.get_by_label('어떤 테스트를 할까요?').fill(AI_REQUEST)
        dialog.get_by_label('어떤 테스트를 할까요?').press('Control+Enter')
        dialog.get_by_role('button', name='✦ AI 테스트 생성').click()
        check = dialog.get_by_text('시작 페이지에서 정확히').first
        expect(check).to_be_visible(timeout=120000)
        check.scroll_into_view_if_needed()  # show the generated steps together with the selector check
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT / 'test-cases.png'))
        page.keyboard.press('Escape')
        expect(dialog).to_be_hidden(timeout=15000)

        nav.get_by_role('button', name=re.compile('^실행 기록')).click()
        page.get_by_role('tab', name='실패 분석').click()
        expect(page.get_by_text('AI 분류').first).to_be_visible(timeout=30000)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT / 'results.png'))
        browser.close()


def main():
    for port in (5000, APP_PORT):
        if not port_free(port):
            raise SystemExit(f'포트 {port}가 사용 중입니다. 실행 중인 데모나 QA 앱을 종료한 뒤 다시 실행하세요.')
    WORK.mkdir(parents=True, exist_ok=True)
    seed(WORK / 'demo.db')
    demo_server = make_server('127.0.0.1', 5000, create_app(WORK / 'demo.db'))
    threading.Thread(target=demo_server.serve_forever, daemon=True).start()
    app = None
    try:
        demo = prepare()
        app = subprocess.Popen(
            [
                sys.executable,
                '-m',
                'streamlit',
                'run',
                str(ROOT / 'streamlit_app.py'),
                '--server.address',
                '127.0.0.1',
                '--server.port',
                str(APP_PORT),
                '--server.headless',
                'true',
                '--browser.gatherUsageStats',
                'false',
            ],
            cwd=ROOT,
            env=os.environ.copy(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        wait_for(f'http://127.0.0.1:{APP_PORT}/_stcore/health')
        capture(demo)
        print('saved to', OUT)
    finally:
        if app:
            app.terminate()
            app.wait(timeout=15)
        demo_server.shutdown()


if __name__ == '__main__':
    main()
