import threading
from unittest.mock import patch
import pytest
from qa_system import background


@pytest.fixture(autouse=True)
def fresh_jobs(monkeypatch):
    monkeypatch.setattr(background, '_jobs', {})


def test_run_reports_progress_and_blocks_a_second_run_of_the_same_project():
    gate = threading.Event()
    seen = []

    def fake_run(case_ids, variant, project_id, progress):
        progress(1, 2)
        seen.append((project_id, background.active_job(project_id)['done']))
        gate.wait(10)
        progress(2, 2)
        return 'run-a'

    with patch('qa_system.background.run_suite', side_effect=fake_run):
        job_id = background.start(7, ['a', 'b'])
        with pytest.raises(ValueError, match='이미 실행 중'):
            background.start(7, ['a'])
        other = background.start(8, [])  # another project may run at the same time
        gate.set()
        finished = background.wait(job_id, timeout=10)
        background.wait(other, timeout=10)
    assert sorted(seen) == [(7, 1), (8, 1)]  # both projects ran at once, each reporting its own progress
    assert finished['phase'] == 'finished' and finished['run_id'] == 'run-a' and finished['done'] == 2
    assert background.active_job(7) is None
    assert 'thread' not in finished


def test_errors_are_kept_for_the_page_instead_of_lost_with_the_thread():
    with patch('qa_system.background.run_suite', side_effect=ValueError("'로그인' 테스트 내용을 검토하고 승인하세요.")):
        job = background.wait(background.start(3, ['x']), timeout=10)
    assert job['phase'] == 'failed' and '승인하세요' in job['error']
    assert background.active_job(3) is None


def test_analysis_runs_only_when_requested_and_there_are_failures():
    with (
        patch('qa_system.background.run_suite', return_value='run-b'),
        patch('qa_system.failure_analysis.failures', return_value=[{'id': 1}]),
        patch('qa_system.failure_analysis.analyze_run', return_value=(0, ['테스트: RuntimeError'])) as analyze,
    ):
        quiet = background.wait(background.start(4, ['x'], analyze=False), timeout=10)
        analysed = background.wait(background.start(4, ['x'], analyze=True), timeout=10)
    assert analyze.call_count == 1
    assert quiet['warnings'] == [] and analysed['warnings'] == ['테스트: RuntimeError']
    assert analysed['phase'] == 'finished'
