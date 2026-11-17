"""Run tests (and the AI failure analysis) in a background thread so the app stays usable meanwhile.

Jobs live in this server process. If the app restarts mid-run, the run row stays RUNNING until
storage.recover_stale_runs() closes it after its time limit.
"""

import threading
import uuid

from qa_system import failure_analysis
from qa_system.runner import run_suite

ACTIVE = ('starting', 'running', 'analyzing')
_jobs = {}
_lock = threading.Lock()


def start(project_id, case_ids, variant='normal', analyze=False):
    """Start a run and return its job id. Raises ValueError if this project already has a run going."""
    with _lock:
        if any(j['project_id'] == project_id and j['phase'] in ACTIVE for j in _jobs.values()):
            raise ValueError('이 프로젝트의 테스트가 이미 실행 중입니다. 끝난 뒤 다시 실행하세요.')
        job_id = uuid.uuid4().hex[:12]
        job = {
            'id': job_id,
            'project_id': project_id,
            'phase': 'starting',
            'done': 0,
            'total': len(case_ids),
            'run_id': None,
            'error': None,
            'warnings': [],
        }
        _jobs[job_id] = job

    def progress(done, total):
        job.update(phase='running', done=done, total=total)

    def work():
        try:
            job['run_id'] = run_suite(case_ids, variant, project_id=project_id, progress=progress)
            if analyze and failure_analysis.failures(job['run_id']):
                job['phase'] = 'analyzing'
                _, errors = failure_analysis.analyze_run(job['run_id'])
                job['warnings'] = errors
            job['phase'] = 'finished'
        except Exception as error:  # Shown on the run page instead of being lost with the thread.
            job.update(phase='failed', error=str(error) or type(error).__name__)

    thread = threading.Thread(target=work, name=f'qa-run-{job_id}', daemon=True)
    job['thread'] = thread
    thread.start()
    return job_id


def get(job_id):
    """A snapshot of the job's state, or None for an unknown id."""
    job = _jobs.get(job_id)
    return {k: v for k, v in job.items() if k != 'thread'} if job else None


def active_job(project_id):
    return next((get(j['id']) for j in _jobs.values() if j['project_id'] == project_id and j['phase'] in ACTIVE), None)


def wait(job_id, timeout=None):
    """Block until the job ends (used by tests and scripts)."""
    job = _jobs.get(job_id)
    if job:
        job['thread'].join(timeout)
    return get(job_id)
