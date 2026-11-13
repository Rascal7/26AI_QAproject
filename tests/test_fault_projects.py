import json
import pytest
from qa_system import storage, runner
from qa_system.catalog import CASES
from qa_system.projects import cases, save_case
from scripts.setup_fault_projects import install


def test_fault_projects_are_repeatable_and_isolated(tmp_path, monkeypatch):
    path = tmp_path / 'qa.db'
    monkeypatch.setattr(storage, 'QA_DB', path)
    monkeypatch.setattr(runner, 'QA_DB', path)
    installed = install()
    assert install() == installed
    assert len(cases(1)) == 13
    pid = next(p for p in installed if p != 1)
    assert len(cases(pid)) == 3
    # The same normal contract passes without the fault, and fails with it.
    run = runner.run_suite(['TC-DB-001', installed[1][0]], project_id=1)
    results = storage.rows('SELECT outcome,details FROM test_results WHERE run_id=? ORDER BY id', (run,))
    assert [r['outcome'] for r in results] == ['PASS', 'FAIL']
    assert [json.loads(r['details'])['target_variant'] for r in results] == ['normal', 'skip_disabled']
    with pytest.raises(ValueError, match='결함'):
        save_case(1, CASES['TC-DB-001']['requirement_id'], dict(CASES['TC-DB-001'], fault_variant='arbitrary'))
