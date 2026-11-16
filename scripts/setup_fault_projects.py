"""Install reproducible fault examples without changing the normal demo server."""

import json
import sqlite3
from datetime import datetime
from qa_system import storage
from qa_system.catalog import CASES, TARGET
from qa_system.projects import create_project, save_requirement, save_case, cases


def install():
    storage.initialize()
    backup = (
        storage.QA_DB.parent / 'backups' / ('qa-before-faults-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.db')
    )
    backup.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(storage.QA_DB) as source, sqlite3.connect(backup) as dest:
        source.backup(dest)
    found = storage.rows('SELECT id FROM projects WHERE name=? AND mode=?', ('DB 오류 재현 QA', 'demo'))
    pid = (
        found[0]['id']
        if found
        else create_project(
            'DB 오류 재현 QA',
            TARGET,
            'DB 데이터 무결성과 계정 상태 반영을 검증합니다. 손상 데이터는 503으로 안내하고, 삭제·비활성 계정은 접근을 차단해야 합니다.',
            '학습용 의도적 결함 3개가 포함됩니다. 테스트마다 별도의 임시 SQLite DB와 데모 서버를 생성합니다. 정상 기준을 만족하지 못하면 FAIL입니다.',
            mode='demo',
        )
    )
    groups = {
        storage.restore_demo(): [
            (
                'login-disabled',
                '비활성 계정 로그인 차단',
                '비활성 계정은 403으로 거절하고 세션을 만들지 않는다.',
                'TC-DB-001',
                'skip_disabled',
                '[결함 재현] 비활성 계정으로 로그인 성공',
            ),
            (
                'login-locked',
                '잠금 계정 로그인 차단',
                '잠금 기간이 남은 계정은 403으로 거절한다.',
                'TC-DB-002',
                'skip_lock',
                '[결함 재현] 잠긴 계정으로 로그인 성공',
            ),
            (
                'login-deleted',
                '삭제 계정 세션 종료',
                '로그인 후 계정을 삭제하면 홈 접근을 차단하고 세션을 종료한다.',
                'TC-DB-004',
                'skip_revalidation',
                '[결함 재현] 삭제 계정의 로그인 세션 유지',
            ),
        ],
        pid: [
            (
                'db-hash',
                '손상된 인증 데이터 처리',
                'DB 비밀번호 해시 손상은 잘못된 비밀번호와 구분하여 503 AUTH_DATA_ERROR로 처리한다.',
                'TC-DB-003',
                'misclassify_hash',
                '[결함 재현] 손상된 DB 해시를 비밀번호 오류로 오인',
            ),
            (
                'db-delete',
                'DB 삭제 결과 반영',
                'DB에서 삭제된 사용자 레코드가 다음 홈 요청부터 접근 권한에 반영된다.',
                'TC-DB-004',
                'skip_revalidation',
                '[결함 재현] 삭제된 사용자 레코드의 접근 권한 유지',
            ),
            (
                'db-status',
                'DB 계정 상태 반영',
                'DB status가 disabled이면 인증에 성공해도 접근을 허용하지 않는다.',
                'TC-DB-001',
                'skip_disabled',
                '[결함 재현] DB 비활성 상태를 무시하고 접근 허용',
            ),
        ],
    }
    result = {}
    for project_id, entries in groups.items():
        existing = {c.get('fault_key'): c['id'] for c in cases(project_id) if c.get('fault_key')}
        result[project_id] = []
        for key, title, spec, baseline, variant, description in entries:
            if key not in existing:
                rid = save_requirement(
                    project_id,
                    title,
                    spec,
                    '의도적으로 결함을 주입한 테스트입니다. 기대 결과는 정상 계약을 유지하며 결함 발견 시 FAIL로 기록합니다.',
                )
                existing[key] = save_case(
                    project_id,
                    rid,
                    dict(
                        CASES[baseline],
                        baseline_id=baseline,
                        engine='demo',
                        fault_variant=variant,
                        fault_key=key,
                        description=description,
                    ),
                    reviewed=True,
                )
            result[project_id].append(existing[key])
    return result


if __name__ == '__main__':
    print(json.dumps(install(), ensure_ascii=False))
