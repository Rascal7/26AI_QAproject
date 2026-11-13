import json
import os
from pathlib import Path
from datetime import datetime, timezone
from demo_web.db import ROOT, connect
from qa_system.catalog import CASES, SCENARIOS, TARGET
from qa_system.evidence import redact

QA_DB = Path(os.environ.get('QA_DB_PATH', ROOT / 'data/qa.db'))


def now():
    return datetime.now(timezone.utc).isoformat()


def encode(value):
    return json.dumps(redact(value), ensure_ascii=False)


def initialize(path=None):
    path = path or QA_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY, name TEXT NOT NULL, target_url TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS requirements(id TEXT PRIMARY KEY, project_id INTEGER REFERENCES projects(id), spec TEXT, version TEXT);
        CREATE TABLE IF NOT EXISTS db_scenarios(scenario_id TEXT PRIMARY KEY, version TEXT, definition TEXT);
        CREATE TABLE IF NOT EXISTS test_cases(id TEXT PRIMARY KEY, requirement_id TEXT REFERENCES requirements(id),
          scenario_id TEXT REFERENCES db_scenarios(scenario_id), source TEXT, definition TEXT, reviewed INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS test_runs(run_id TEXT PRIMARY KEY, project_id INTEGER REFERENCES projects(id), target_url TEXT,
          variant TEXT, seed_version TEXT, started_at TEXT, finished_at TEXT, status TEXT, snapshots TEXT, code_snapshot TEXT);
        CREATE TABLE IF NOT EXISTS test_results(id INTEGER PRIMARY KEY, run_id TEXT REFERENCES test_runs(run_id),
          case_id TEXT REFERENCES test_cases(id), scenario_id TEXT REFERENCES db_scenarios(scenario_id),
          setup_status TEXT, outcome TEXT, details TEXT);
        CREATE TABLE IF NOT EXISTS bug_reports(id INTEGER PRIMARY KEY, result_id INTEGER REFERENCES test_results(id),
          title TEXT, facts TEXT, hypothesis TEXT);
        CREATE TABLE IF NOT EXISTS reports(run_id TEXT PRIMARY KEY REFERENCES test_runs(run_id), markdown TEXT, ai_analysis TEXT);
        CREATE TABLE IF NOT EXISTS app_meta(key TEXT PRIMARY KEY, value TEXT);
        ''')
        # Additive migration preserves every existing execution and its foreign keys.
        additions = {'projects': {'overview': "TEXT NOT NULL DEFAULT ''", 'exceptions': "TEXT NOT NULL DEFAULT ''",
                                 'mode': "TEXT NOT NULL DEFAULT 'web'", 'tags': "TEXT NOT NULL DEFAULT '[]'"},
                     'requirements': {'title': "TEXT NOT NULL DEFAULT ''", 'exceptions': "TEXT NOT NULL DEFAULT ''"},
                     'test_cases': {'project_id': 'INTEGER REFERENCES projects(id)'}}
        for table, columns in additions.items():
            present = {r['name'] for r in db.execute(f'PRAGMA table_info({table})')}
            for name, definition in columns.items():
                if name not in present:
                    db.execute(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')
        if db.execute("SELECT 1 FROM app_meta WHERE key='baseline_seeded'").fetchone():
            return
        db.execute('INSERT OR IGNORE INTO projects(id,name,target_url,mode) VALUES(1,?,?,?)', ('로그인 데모', TARGET, 'demo'))
        db.execute("UPDATE projects SET mode='demo' WHERE id=1")
        for key, scenario in SCENARIOS.items():
            db.execute('INSERT OR IGNORE INTO db_scenarios VALUES(?,?,?)', (key, '1.0', encode(scenario)))
        for key, case in CASES.items():
            db.execute('INSERT OR IGNORE INTO requirements(id,project_id,spec,version) VALUES(?,1,?,?)', (case['requirement_id'], encode(case), '1.0'))
            db.execute("UPDATE requirements SET title=? WHERE id=? AND title=''", (case['description'],case['requirement_id']))
            db.execute('INSERT OR IGNORE INTO test_cases(id,requirement_id,scenario_id,source,definition,reviewed) VALUES(?,?,?,?,?,1)',
                       (key, case['requirement_id'], case['scenario_id'], 'human', encode(case)))
        db.execute('UPDATE test_cases SET project_id=(SELECT project_id FROM requirements WHERE requirements.id=test_cases.requirement_id) WHERE project_id IS NULL')
        db.execute("INSERT INTO app_meta VALUES('baseline_seeded','1')")


def rows(sql, params=()):
    initialize()
    with connect(QA_DB) as db:
        return [dict(r) for r in db.execute(sql, params).fetchall()]


def save_ai_case(case):
    from qa_system.catalog import validate_case
    import re
    if validate_case(case):
        raise ValueError(validate_case(case))
    if not re.fullmatch(r'AI-[A-Za-z0-9_-]{1,80}', case['id']):
        raise ValueError('AI 테스트 ID는 AI-로 시작해야 합니다.')
    case = dict(case, source='ai')
    initialize()
    with connect(QA_DB) as db:
        db.execute('INSERT INTO test_cases(id,requirement_id,scenario_id,source,definition,reviewed,project_id) VALUES(?,?,?,?,?,1,1) ON CONFLICT(id) DO UPDATE SET requirement_id=excluded.requirement_id, scenario_id=excluded.scenario_id, definition=excluded.definition, reviewed=1',
                   (case['id'], case['requirement_id'], case['scenario_id'], 'ai', encode(case)))


def get_case(case_id):
    found = rows('SELECT definition FROM test_cases WHERE id=?', (case_id,))
    if not found:
        raise ValueError('저장된 테스트가 없습니다.')
    return json.loads(found[0]['definition'])
