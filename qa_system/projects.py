import json
import uuid
from urllib.parse import urlsplit
from demo_web.db import connect
from qa_system import sharing, storage


def validate_url(value):
    parsed = urlsplit(value.strip())
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('http:// 또는 https://로 시작하는 웹 주소를 입력하세요. 인증정보는 URL에 넣을 수 없습니다.')
    sharing.check_target(value.strip())
    return value.strip()


def get_project(project_id):
    found = storage.rows('SELECT * FROM projects WHERE id=?', (project_id,))
    if not found:
        raise ValueError('프로젝트가 없습니다.')
    return found[0]


def normalize_tags(value):
    values = value.split(',') if isinstance(value, str) else value
    return list(dict.fromkeys(t.strip().lstrip('#').strip() for t in values if t.strip().lstrip('#').strip()))


def create_project(name, url, overview='', exceptions='', *, mode='web', tags=()):
    if mode not in ('web', 'demo'):
        raise ValueError('지원하지 않는 프로젝트 유형입니다.')
    if not name.strip():
        raise ValueError('프로젝트 이름을 입력하세요.')
    url = validate_url(url)
    storage.initialize()
    with connect(storage.QA_DB) as db:
        return db.execute(
            'INSERT INTO projects(name,target_url,overview,exceptions,mode,tags) VALUES(?,?,?,?,?,?)',
            (name.strip(), url, overview, exceptions, mode, json.dumps(normalize_tags(tags), ensure_ascii=False)),
        ).lastrowid


def save_project(project_id, name, overview, exceptions, tags=None):
    get_project(project_id)
    if not name.strip():
        raise ValueError('프로젝트 이름을 입력하세요.')
    with connect(storage.QA_DB) as db:
        db.execute(
            'UPDATE projects SET name=?,overview=?,exceptions=? WHERE id=?',
            (name.strip(), overview, exceptions, project_id),
        )
        if tags is not None:
            db.execute(
                'UPDATE projects SET tags=? WHERE id=?',
                (json.dumps(normalize_tags(tags), ensure_ascii=False), project_id),
            )


def save_requirement(project_id, title, spec, exceptions='', requirement_id=None):
    get_project(project_id)
    if not title.strip() or not spec.strip():
        raise ValueError('요구사항 이름과 기대 동작을 입력하세요.')
    requirement_id = requirement_id or 'REQ-' + uuid.uuid4().hex[:12]
    with connect(storage.QA_DB) as db:
        existing = db.execute('SELECT project_id FROM requirements WHERE id=?', (requirement_id,)).fetchone()
        if existing and existing['project_id'] != project_id:
            raise ValueError('다른 프로젝트의 요구사항입니다.')
        db.execute(
            'INSERT INTO requirements(id,project_id,title,spec,exceptions,version) VALUES(?,?,?,?,?,?) '
            'ON CONFLICT(id) DO UPDATE SET title=excluded.title,spec=excluded.spec,exceptions=excluded.exceptions,version=excluded.version',
            (requirement_id, project_id, title.strip(), spec, exceptions, storage.now()),
        )
    return requirement_id


def requirements(project_id):
    return storage.rows('SELECT * FROM requirements WHERE project_id=? ORDER BY rowid', (project_id,))


def cases(project_id, requirement_id=None):
    sql = 'SELECT * FROM test_cases WHERE project_id=?'
    args = [project_id]
    if requirement_id:
        sql += ' AND requirement_id=?'
        args.append(requirement_id)
    return [
        dict(
            json.loads(r['definition']),
            id=r['id'],
            requirement_id=r['requirement_id'],
            reviewed=bool(r['reviewed']),
            project_id=project_id,
        )
        for r in storage.rows(sql + ' ORDER BY rowid', args)
    ]


def save_case(project_id, requirement_id, definition, reviewed=False):
    project = get_project(project_id)
    if requirement_id not in {r['id'] for r in requirements(project_id)}:
        raise ValueError('프로젝트에 속한 요구사항을 선택하세요.')
    definition = dict(definition)
    from demo_web.app import VARIANTS

    if 'fault_variant' in definition and (
        project['mode'] != 'demo'
        or definition.get('engine') == 'web'
        or definition['fault_variant'] not in VARIANTS[1:]
    ):
        raise ValueError('결함 재현은 허용된 데모 결함 버전만 사용할 수 있습니다.')
    if not isinstance(definition.get('description'), str) or not definition['description'].strip():
        raise ValueError('테스트 이름을 입력하세요.')
    if definition.get('engine') == 'web':
        from qa_system.web_tests import validate_steps

        validate_steps(definition['steps'], project['target_url'])
    else:
        from qa_system.catalog import CASES, validate_case

        baseline = CASES.get(definition.get('baseline_id', definition.get('id')))
        if project['mode'] != 'demo' or not baseline:
            raise ValueError('DB fixture 테스트는 로그인 데모 프로젝트에서만 사용할 수 있습니다.')
        checked = dict(definition, requirement_id=baseline['requirement_id'])
        error = validate_case(checked)
        if error:
            raise ValueError(error)
    case_id = 'CASE-' + uuid.uuid4().hex[:12]
    definition.update(id=case_id, requirement_id=requirement_id, project_id=project_id)
    definition.setdefault('scenario_id', None)
    definition.setdefault('source', 'human')
    with connect(storage.QA_DB) as db:
        db.execute(
            'INSERT INTO test_cases(id,requirement_id,scenario_id,source,definition,reviewed,project_id) VALUES(?,?,?,?,?,?,?)',
            (
                case_id,
                requirement_id,
                definition['scenario_id'],
                definition['source'],
                storage.encode(definition),
                int(reviewed),
                project_id,
            ),
        )
    return case_id


def approve_case(project_id, case_id):
    with connect(storage.QA_DB) as db:
        changed = db.execute(
            'UPDATE test_cases SET reviewed=1 WHERE id=? AND project_id=?', (case_id, project_id)
        ).rowcount
        if not changed:
            raise ValueError('프로젝트의 테스트가 아닙니다.')


def delete_project(project_id):
    """Remove owned database records atomically; keep local evidence files as archives."""
    storage.initialize()
    storage.recover_stale_runs()
    with connect(storage.QA_DB) as db:
        db.execute('BEGIN IMMEDIATE')
        if not db.execute('SELECT 1 FROM projects WHERE id=?', (project_id,)).fetchone():
            raise ValueError('프로젝트가 없습니다.')
        if db.execute("SELECT 1 FROM test_runs WHERE project_id=? AND status='RUNNING'", (project_id,)).fetchone():
            raise ValueError('테스트가 실행 중입니다. 실행이 끝난 뒤 삭제하세요.')
        runs = 'SELECT run_id FROM test_runs WHERE project_id=?'
        db.execute(
            f'DELETE FROM bug_reports WHERE result_id IN (SELECT id FROM test_results WHERE run_id IN ({runs}))',
            (project_id,),
        )
        for table in ('reports', 'test_results'):
            db.execute(f'DELETE FROM {table} WHERE run_id IN ({runs})', (project_id,))
        for table in ('test_runs', 'test_cases', 'requirements'):
            db.execute(f'DELETE FROM {table} WHERE project_id=?', (project_id,))
        db.execute('DELETE FROM projects WHERE id=?', (project_id,))
