import pytest
from qa_system.contracts import execute_case


@pytest.mark.parametrize('case_id', [f'TC-LOGIN-{n:03}' for n in range(1, 6)])
def test_login(qa_env, case_id):
    execute_case(qa_env, case_id)


def test_logout_from_home_ends_session(qa_env):
    from playwright.sync_api import expect
    from demo_web.seed import EMAIL, PASSWORD
    from qa_system.contracts import session_present

    page, url = qa_env['page'], qa_env['url']
    page.goto(url + '/login')
    page.get_by_test_id('email-input').fill(EMAIL)
    page.get_by_test_id('password-input').fill(PASSWORD)
    page.get_by_test_id('login-submit').click()
    expect(page).to_have_url(url + '/home')
    page.get_by_test_id('logout-button').click()
    expect(page).to_have_url(url + '/login')
    assert not session_present(qa_env)
    page.goto(url + '/home')
    expect(page).to_have_url(url + '/login')
