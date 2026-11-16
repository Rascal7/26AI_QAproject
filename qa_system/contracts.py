"""Reviewed browser assertions shared by human and restricted AI-generated tests."""

from playwright.sync_api import expect
from demo_web.app import AUTH_MESSAGE, UNAVAILABLE_MESSAGE, ERROR_MESSAGE
from demo_web.seed import EMAIL, PASSWORD, WRONG_PASSWORD
from qa_system.catalog import CASES


def session_present(env):
    app = env['app']
    cookies = env['page'].context.cookies()
    value = next((c['value'] for c in cookies if c['name'] == app.config['SESSION_COOKIE_NAME']), None)
    if not value:
        return False
    # Server-side signer, in-process only. Never expose or record raw cookie values.
    serializer = app.session_interface.get_signing_serializer(app)
    return bool(serializer.loads(value).get('user_id'))


def execute_case(env, case_id):
    contract = CASES[case_id]
    page, result, db, url = (env[k] for k in ('page', 'result', 'db', 'url'))
    result.update(case_id=case_id, scenario_id=contract['scenario_id'], expected=contract)
    try:
        result['before'] = db.prepare(contract['scenario_id'])
    except Exception:
        result['setup_status'] = 'failed'
        raise
    page.goto(url + '/login')
    emails = {'TC-LOGIN-003': '', 'TC-LOGIN-005': 'missing@example.com'}
    passwords = {'TC-LOGIN-002': WRONG_PASSWORD, 'TC-LOGIN-004': ''}
    page.get_by_test_id('email-input').fill(emails.get(case_id, EMAIL))
    page.get_by_test_id('password-input').fill(passwords.get(case_id, PASSWORD))
    if case_id == 'TC-DB-005':
        result['duplicate_rejected'] = db.reject_duplicate()
        result['observations'].append('중복 INSERT 무결성 오류 및 롤백, 원본 필드·해시 동일성 확인')
    requests = []
    page.on(
        'request', lambda r: requests.append(r.method) if r.method == 'POST' and r.url == url + '/api/login' else None
    )
    if case_id in ('TC-LOGIN-003', 'TC-LOGIN-004'):
        field = 'email' if case_id.endswith('003') else 'password'
        message = '이메일을 입력하세요.' if field == 'email' else '비밀번호를 입력하세요.'
        page.get_by_test_id('login-submit').click()
        expect(page.get_by_test_id('login-form')).to_have_attribute('data-state', 'invalid')
        expect(page.get_by_test_id(f'{field}-error')).to_have_text(message)
        expect(page.get_by_test_id(f'{field}-input')).to_be_focused()
        page.wait_for_timeout(500)  # Explicit requirement: observe zero requests for 500 ms.
        result['request_count'] = len(requests)
        assert len(requests) == 0, '클라이언트 검증 실패 시 요청은 0회여야 합니다.'
        expect(page).to_have_url(url + '/login')
        assert not session_present(env), '인증 세션이 없어야 합니다.'
        page.goto(url + '/home')
        expect(page).to_have_url(url + '/login')
    else:
        with page.expect_response(
            lambda r: r.url == url + '/api/login' and r.request.method == 'POST'
        ) as response_info:
            page.get_by_test_id('login-submit').click(no_wait_after=True)
        response = response_info.value
        assert len(env['response_bodies']) == 1
        body = env['response_bodies'][0]
        result['http'].append(
            {
                'endpoint': '/api/login',
                'status': response.status,
                'body': body,
                'body_source': 'real_server_response_observer',
            }
        )
        result['request_count'] = len(requests)
        expected_login_status = 200 if case_id == 'TC-DB-004' else contract['expected_status']
        assert response.status == expected_login_status, f'기대 HTTP {expected_login_status} / 실제 {response.status}'
        assert len(requests) == 1, '로그인 요청은 1회여야 합니다.'
        if response.status == 200:
            assert body['ok'] is True
            expect(page).to_have_url(url + '/home')
            expect(page.get_by_test_id('home-title')).to_have_text('로그인 완료')
            expect(page.get_by_test_id('welcome-message')).to_have_text('테스트 사용자님, 환영합니다.')
            assert session_present(env), '인증 세션이 필요합니다.'
            if case_id == 'TC-DB-004':
                db.delete_user()
                with page.expect_response(lambda r: r.url == url + '/home') as home_info:
                    page.reload()
                result['http'].append({'endpoint': '/home', 'status': home_info.value.status})
                assert home_info.value.status == 302, f'삭제 후 기대 HTTP 302 / 실제 {home_info.value.status}'
                expect(page).to_have_url(url + '/login')
                assert not session_present(env), '삭제된 사용자의 세션을 제거해야 합니다.'
                page.goto(url + '/home')
                expect(page).to_have_url(url + '/login')
            else:
                page.reload()
                expect(page).to_have_url(url + '/home')
                expect(page.get_by_test_id('welcome-message')).to_have_text('테스트 사용자님, 환영합니다.')
        else:
            assert body['ok'] is False
            assert body['error_code'] == contract['expected_error_code']
            message = {401: AUTH_MESSAGE, 403: UNAVAILABLE_MESSAGE, 503: ERROR_MESSAGE}[response.status]
            assert body['message'] == message
            expect(page).to_have_url(url + '/login')
            expect(page.get_by_test_id('login-error')).to_have_text(message)
            expect(page.get_by_test_id('login-form')).to_have_attribute(
                'data-state', 'error' if response.status == 503 else 'rejected'
            )
            expect(page.get_by_test_id('login-submit')).to_be_enabled()
            assert not session_present(env), '거부된 로그인에 세션이 생성되면 안 됩니다.'
            # Keep the error screen as evidence before testing protected-page access.
            result['observations'].append(message)
            page.goto(url + '/home')
            expect(page).to_have_url(url + '/login')
    after = db.snapshot()
    if case_id != 'TC-DB-004':
        assert after == result['before'], '테스트 후 DB 상태가 유지되어야 합니다.'
    result['session'] = 'present' if session_present(env) else 'absent'
    assert result['session'] == contract['expected_session']
    result['observations'].append('화면·요청 횟수·보호 경로·서버 세션·DB 사후조건 검증 완료')
