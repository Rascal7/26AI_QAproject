"""Small, reviewable browser language. No generated Python, JavaScript or SQL execution."""
import os
import re
from urllib.parse import urljoin, urlsplit
from playwright.sync_api import expect

ACTIONS = {'navigate','assert_status','assert_visible','assert_text','assert_url','fill','click','press'}
ASSERTIONS = {'assert_status','assert_visible','assert_text','assert_url'}


def origin(url):
    parts = urlsplit(url)
    return (parts.scheme, parts.hostname, parts.port or (443 if parts.scheme == 'https' else 80))


def target_url(base, value):
    target = urljoin(base, value or base)
    p = urlsplit(target)
    if p.scheme not in ('http','https') or p.username or p.password or origin(target) != origin(base):
        raise ValueError('프로젝트 URL과 같은 사이트의 경로만 사용할 수 있습니다.')
    return target


def validate_steps(steps, base):
    if not isinstance(steps, list) or not 1 <= len(steps) <= 20:
        raise ValueError('실행 단계는 1~20개여야 합니다.')
    if not any(s.get('action') in ASSERTIONS for s in steps if isinstance(s, dict)):
        raise ValueError('결과 확인 단계가 하나 이상 필요합니다.')
    for step in steps:
        if not isinstance(step, dict) or step.get('action') not in ACTIONS:
            raise ValueError('허용되지 않은 브라우저 동작입니다.')
        selector, value = step.get('selector',''), step.get('value','')
        if not isinstance(selector,str) or not isinstance(value,str) or max(len(selector),len(value)) > 2000:
            raise ValueError('선택자와 값은 2,000자 이하 문자열이어야 합니다.')
        if step['action'] in {'assert_visible','assert_text','fill','click','press'} and not selector.strip():
            raise ValueError('대상 요소 선택자가 필요합니다.')
        if step['action'] in {'navigate','assert_url'}:
            target_url(base, value)
        if step['action'] == 'assert_status' and (not value.isdigit() or not 100 <= int(value) <= 599):
            raise ValueError('HTTP 기대값은 100~599여야 합니다.')
        if step['action'] == 'press' and value not in ('Enter','Tab','Escape'):
            raise ValueError('Enter, Tab, Escape 키만 사용할 수 있습니다.')
    return steps


def template_cases():
    return {
        'page': {'description':'페이지 접속', 'summary':'정상 응답 확인', 'steps':[
            {'action':'navigate','selector':'','value':''}, {'action':'assert_status','selector':'','value':'200'}]},
        'visible': {'description':'요소 표시', 'summary':'버튼·입력창 확인', 'steps':[
            {'action':'navigate','selector':'','value':''}, {'action':'assert_visible','selector':'h1','value':''}]},
        'text': {'description':'문구 확인', 'summary':'기대 문구 비교', 'steps':[
            {'action':'navigate','selector':'','value':''}, {'action':'assert_text','selector':'h1','value':'기대 문구'}]},
        'click': {'description':'클릭 후 이동', 'summary':'링크와 이동 경로 확인', 'steps':[
            {'action':'navigate','selector':'','value':''}, {'action':'click','selector':'a','value':''},
            {'action':'assert_url','selector':'','value':'/next'}]},
        'form': {'description':'입력 후 안내', 'summary':'폼 입력과 결과 확인', 'steps':[
            {'action':'navigate','selector':'','value':''}, {'action':'fill','selector':'input[name=email]','value':'sample@example.com'},
            {'action':'click','selector':'button[type=submit]','value':''},
            {'action':'assert_text','selector':'[role=alert]','value':'기대 안내 문구'}]}
    }


def execute_web_case(env, definition, base):
    steps = validate_steps(definition['steps'], base)
    page, result = env['page'], env['result']
    result.update(case_id=definition['id'], scenario_id=None, expected=definition, engine='web', steps=steps)
    # Browser navigations stay on the explicitly registered site; remote assets may load normally.
    def restrict(route):
        if route.request.is_navigation_request() and origin(route.request.url) != origin(base):
            route.abort()
        else:
            route.continue_()
    page.route('**/*', restrict)
    observed = {'response':None}
    def response_observer(response):
        if response.request.is_navigation_request() and response.request.frame == page.main_frame:
            observed['response'] = response
            result['http'].append({'endpoint':urlsplit(response.url).path, 'status':response.status})
    page.on('response',response_observer)
    for index, step in enumerate(steps):
        action, selector, value = step['action'], step.get('selector',''), step.get('value','')
        locator = page.locator(selector) if selector else None
        if action == 'navigate':
            page.goto(target_url(base,value), wait_until='domcontentloaded')
        elif action == 'assert_status':
            current_response = observed['response']
            if current_response is None:
                raise ValueError('HTTP 확인 전에 페이지 이동 단계가 필요합니다.')
            assert current_response.status == int(value), f'기대 HTTP {value} / 실제 {current_response.status}'
        elif action == 'assert_visible':
            expect(locator).to_be_visible()
        elif action == 'assert_text':
            expect(locator).to_contain_text(value)
        elif action == 'assert_url':
            expect(page).to_have_url(target_url(base,value))
        elif action == 'fill':
            secret_match = re.fullmatch(r'\$\{(QA_TEST_[A-Z0-9_]+)\}',value)
            if secret_match:
                value = os.getenv(secret_match[1], '')
                if not value:
                    raise ValueError('테스트 입력용 환경변수가 설정되지 않았습니다.')
                env['secrets'].append(value)
            # Leaving a password empty is a normal validation test, not a secret.
            if value and locator.get_attribute('type') == 'password' and not secret_match:
                raise ValueError('비밀번호는 ${QA_TEST_PASSWORD} 환경변수 참조를 사용하세요.')
            locator.fill(value)
        elif action == 'click':
            locator.click()
        elif action == 'press':
            locator.press(value)
        result['observations'].append(f'{index+1}. {action} 확인')
