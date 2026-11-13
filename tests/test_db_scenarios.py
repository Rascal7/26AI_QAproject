import pytest
from qa_system.contracts import execute_case


@pytest.mark.parametrize('case_id', [f'TC-DB-{n:03}' for n in range(1, 6)])
def test_db_scenario(qa_env, case_id):
    execute_case(qa_env, case_id)
