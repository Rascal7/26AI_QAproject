"""Human-owned contracts. AI output never replaces expected results."""

VERSION = '1.0'
TARGET = 'http://127.0.0.1:5000'
TITLES = [
    '정상 로그인',
    '잘못된 비밀번호',
    '빈 이메일',
    '빈 비밀번호',
    '없는 계정',
    '비활성 계정',
    '잠긴 계정',
    '잘못 저장된 해시',
    '로그인 후 계정 삭제',
    '중복 이메일 거부',
]
CASES = {}
for index, title in enumerate(TITLES):
    group, n = ('LOGIN', index + 1) if index < 5 else ('DB', index - 4)
    case_id = f'TC-{group}-{n:03}'
    status = [200, 401, None, None, 401, 403, 403, 503, 302, 200][index]
    code = [
        None,
        'INVALID_CREDENTIALS',
        None,
        None,
        'INVALID_CREDENTIALS',
        'ACCOUNT_UNAVAILABLE',
        'ACCOUNT_UNAVAILABLE',
        'AUTH_DATA_ERROR',
        None,
        None,
    ][index]
    CASES[case_id] = dict(
        id=case_id,
        requirement_id=f'REQ-{group}-{n:03}',
        scenario_id=f'DB-{n:03}' if group == 'DB' else None,
        description=title,
        expected_status=status,
        expected_error_code=code,
        expected_session='present' if index in (0, 9) else 'absent',
        source='human',
        version=VERSION,
        steps=['새 테스트 DB와 브라우저 준비', title, 'HTTP·화면·세션·DB 계약 검증'],
    )

SCENARIOS = {
    f'DB-{n:03}': dict(
        scenario_id=f'DB-{n:03}',
        version=VERSION,
        description=TITLES[n + 4],
        fixture_key=['disabled', 'locked', 'invalid_hash', 'delete_user', 'duplicate_email'][n - 1],
        preconditions='정상 시드 1명, 별도 연결로 변경 반영 확인',
        timing=['before_login', 'before_login', 'before_login', 'after_login', 'during_test'][n - 1],
        expected=CASES[f'TC-DB-{n:03}'],
    )
    for n in range(1, 6)
}


def validate_case(case):
    baseline = CASES.get(case.get('baseline_id', case.get('id')))
    if baseline is None:
        return '허용된 기준 테스트가 아닙니다. 검토가 필요합니다.'
    for key in ('requirement_id', 'scenario_id', 'expected_status', 'expected_error_code', 'expected_session'):
        if case.get(key) != baseline[key]:
            return f'{key}: 사람이 정한 계약과 다릅니다. 검토가 필요합니다.'
    return None
