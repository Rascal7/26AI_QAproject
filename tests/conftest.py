import json
import logging
import os
import threading
from pathlib import Path
import pytest
from flask import request as flask_request
from werkzeug.serving import make_server, WSGIRequestHandler
from demo_web.app import create_app, VARIANTS
from demo_web.db import ROOT
from tests.db_scenarios import ScenarioDB
from qa_system.evidence import redact, sanitize_trace


class QuietHandler(WSGIRequestHandler):
    def log(self, *args, **kwargs):
        pass


def pytest_addoption(parser):
    parser.addoption('--variant', default='normal', choices=VARIANTS)
    parser.addoption('--result-dir', default=None)
    parser.addoption('--qa-port', type=int, default=0)


@pytest.fixture
def web_env(tmp_path, request, page):
    out = Path(request.config.getoption('--result-dir') or ROOT / 'artifacts/manual')
    out.mkdir(parents=True, exist_ok=True)
    name = request.node.originalname
    result = {'setup_status': 'ready', 'http': [], 'observations': [], 'evidence': {}, 'error': None}
    request.node.qa_result, request.node.qa_path = result, out / f'{name}.json'
    secrets = [v for k, v in os.environ.items() if k.startswith('QA_TEST_') and v]
    request.node.qa_secrets = secrets
    raw = tmp_path / 'trace.zip'
    page.set_default_timeout(5000)
    page.context.tracing.start(screenshots=False, snapshots=False, sources=False)
    try:
        yield {'page': page, 'result': result, 'secrets': secrets}
    finally:
        try:
            if not page.is_closed():
                screenshot = out / f'{name}.png'
                page.screenshot(path=str(screenshot), full_page=True, mask=[page.locator('input,textarea')])
                result['evidence']['screenshot'] = str(screenshot.resolve())
            page.context.tracing.stop(path=str(raw))
            destination = out / f'{name}.trace.zip'
            sanitize_trace(raw, destination, secrets)
            result['evidence']['trace'] = str(destination.resolve())
        finally:
            raw.unlink(missing_ok=True)


@pytest.fixture
def qa_env(tmp_path, request, page):
    out = Path(request.config.getoption('--result-dir') or ROOT / 'artifacts/manual')
    out.mkdir(parents=True, exist_ok=True)
    name = request.node.name.replace('[', '_').replace(']', '')
    if getattr(request.node, 'originalname', '').startswith('test_case_'):
        name = request.node.originalname
    result = {
        'case_id': getattr(request.node.function, 'case_id', name),
        'setup_status': 'pending',
        'http': [],
        'observations': [],
        'before': None,
        'after': None,
        'evidence': {},
        'error': None,
    }
    request.node.qa_result = result
    request.node.qa_path = out / f'{name}.json'
    server = thread = db = None
    trace_started = False
    raw = tmp_path / 'raw-trace.zip'
    try:
        db = ScenarioDB(tmp_path / 'test.sqlite3', tmp_path)
        variant = getattr(request, 'param', request.config.getoption('--variant'))
        result['target_variant'] = variant
        app = create_app(db.path, testing=True, variant=variant)
        response_bodies = []

        @app.after_request
        def observe_response(response):
            # Test-only server observer: Chromium may discard response bodies on navigation.
            # No mocking, interception, extra API, request body or cookie recording.
            if flask_request.path == '/api/login' and response.is_json:
                response_bodies.append(response.get_json())
            return response

        app.logger.setLevel(logging.CRITICAL)
        server = make_server('127.0.0.1', request.config.getoption('--qa-port'), app, request_handler=QuietHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        page.set_default_timeout(5000)
        page.context.tracing.start(screenshots=True, snapshots=False, sources=False)
        trace_started = True
        result['setup_status'] = 'ready'
        yield dict(
            db=db,
            app=app,
            page=page,
            url=f'http://127.0.0.1:{server.server_port}',
            result=result,
            response_bodies=response_bodies,
        )
    finally:
        try:
            if server and not page.is_closed():
                from qa_system.contracts import session_present

                result['session'] = 'present' if session_present({'app': app, 'page': page}) else 'absent'
        except Exception:
            result['session'] = 'unverified'
        if db:
            try:
                result['after'] = db.snapshot()
            except Exception:
                result['observations'].append('DB 사후 조회 실패')
        try:
            if not page.is_closed():
                screenshot = out / f'{name}.png'
                page.screenshot(path=str(screenshot), full_page=True, mask=[page.get_by_test_id('password-input')])
                result['evidence']['screenshot'] = str(screenshot.resolve())
            if trace_started:
                cookies = [c['value'] for c in page.context.cookies()]
                page.context.tracing.stop(path=str(raw))
                destination = out / f'{name}.trace.zip'
                sanitize_trace(raw, destination, cookies)
                result['evidence']['trace'] = str(destination.resolve())
        finally:
            raw.unlink(missing_ok=True)
            if server:
                server.shutdown()
                server.server_close()
            if thread:
                thread.join(timeout=5)
            if db:
                db.path.unlink(missing_ok=True)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    report = (yield).get_result()
    result = getattr(item, 'qa_result', None)
    if result is None:
        return
    if report.failed:
        is_assertion = call.excinfo and isinstance(call.excinfo.value, AssertionError)
        result['outcome'] = (
            'FAIL' if report.when == 'call' and is_assertion and result['setup_status'] == 'ready' else 'ERROR'
        )
        if result['setup_status'] != 'ready':
            result['setup_status'] = 'failed'
        # Avoid pytest source lines / locals containing raw credentials.
        result['error'] = (
            redact(str(call.excinfo.value), getattr(item, 'qa_secrets', ()))[:4000] if call.excinfo else '실행 실패'
        )
    elif report.when == 'call':
        result['outcome'] = 'PASS'
    if report.when == 'teardown':
        result.setdefault('outcome', 'ERROR')
        item.qa_path.write_text(
            json.dumps(redact(result, getattr(item, 'qa_secrets', ())), ensure_ascii=False, indent=2), encoding='utf-8'
        )
