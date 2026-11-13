import pytest
from qa_system.contracts import execute_case


@pytest.mark.parametrize('case_id', [f'TC-LOGIN-{n:03}' for n in range(1, 6)])
def test_login(qa_env, case_id):
    execute_case(qa_env, case_id)
