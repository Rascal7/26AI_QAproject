"""Run the plan's independent-order and injected-defect acceptance checks."""
import json
from demo_web.db import ROOT
from qa_system.catalog import CASES
from qa_system.runner import run_suite
from qa_system.storage import rows


def main():
    summary = []
    experiments = [('normal', list(CASES), None), ('normal', list(reversed(CASES)), None),
                   ('skip_disabled', list(CASES), 'TC-DB-001'), ('skip_lock', list(CASES), 'TC-DB-002'),
                   ('skip_revalidation', list(CASES), 'TC-DB-004')]
    for variant, ids, expected_failure in experiments:
        run_id = run_suite(ids, variant)
        results = rows('SELECT case_id,outcome FROM test_results WHERE run_id=?', (run_id,))
        failures = [r['case_id'] for r in results if r['outcome'] == 'FAIL']
        errors = [r['case_id'] for r in results if r['outcome'] == 'ERROR']
        expected = [expected_failure] if expected_failure else []
        entry = dict(run_id=run_id, variant=variant, failures=failures, errors=errors,
                     acceptance_passed=failures == expected and not errors and len(results) == 10)
        summary.append(entry)
        print(json.dumps(entry), flush=True)
    report = {'experiments': summary, 'false_positives_normal': len(summary[0]['failures']),
              'injected_defects': 3, 'detected_defects': sum(bool(s['failures']) for s in summary[2:]),
              'all_acceptance_passed': all(s['acceptance_passed'] for s in summary)}
    (ROOT / 'artifacts/acceptance.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    assert report['all_acceptance_passed'], 'Acceptance failure: see artifacts/acceptance.json'


if __name__ == '__main__':
    main()
