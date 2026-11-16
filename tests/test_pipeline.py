import json
import zipfile
import pytest
from qa_system.ai import canonical_code, validate_code
from qa_system.catalog import CASES, validate_case
from qa_system.evidence import sanitize_trace
from qa_system.runner import child_environment
from tests.db_scenarios import ScenarioDB


def test_generated_code_cannot_change_contract_or_execute_arbitrary_python():
    valid = canonical_code('TC-DB-001')
    assert validate_code(valid, 'TC-DB-001') == valid
    for code in [valid + '\nimport os\n', valid.replace('TC-DB-001', 'TC-LOGIN-001'),
                 valid.replace("'TC-DB-001'", "__import__('os').getcwd()"),
                 'def test_generated(qa_env):\n    pass\n']:
        with pytest.raises(ValueError):
            validate_code(code, 'TC-DB-001')
    altered = dict(CASES['TC-DB-001'], expected_status=200)
    assert validate_case(altered)
    assert validate_case(dict(CASES['TC-DB-001'], scenario_id='DB-999'))


def test_db_path_guard_preserves_existing_files(tmp_path):
    path = tmp_path / 'demo.db'
    path.write_text('must survive', encoding='utf-8')
    with pytest.raises(ValueError):
        ScenarioDB(path, tmp_path)
    assert path.read_text(encoding='utf-8') == 'must survive'
    db = ScenarioDB(tmp_path / 'test.sqlite3', tmp_path)
    assert db.snapshot()['count'] == 1
    with pytest.raises(ValueError):
        ScenarioDB(db.path, tmp_path)


def test_api_secrets_not_in_test_environment(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-secret')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'test-secret')
    monkeypatch.setenv('PYTEST_ADDOPTS', '-p evil')
    env = child_environment()
    assert not {'OPENAI_API_KEY', 'AWS_SECRET_ACCESS_KEY', 'PYTEST_ADDOPTS'} & env.keys()


def test_trace_redaction(tmp_path):
    raw, out = tmp_path / 'raw.zip', tmp_path / 'clean.zip'
    with zipfile.ZipFile(raw, 'w') as z:
        z.writestr('trace.trace', json.dumps({'params': {'value': 'QaDemo!234'}, 'cookie': 'session-value'}) + '\n')
        z.writestr('trace.network', 'password and cookie body')
        z.writestr('resources/secret-body', 'QaDemo!234')
    sanitize_trace(raw, out)
    with zipfile.ZipFile(out) as z:
        assert 'resources/secret-body' not in z.namelist()
        assert z.read('trace.network') == b''
        assert b'QaDemo!234' not in z.read('trace.trace')
        assert b'session-value' not in z.read('trace.trace')
