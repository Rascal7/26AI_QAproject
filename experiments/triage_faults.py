"""Check that AI failure analysis recognises real product defects.

Runs the intentional-fault demo tests (inactive account allowed, lock ignored, deleted user keeps a session,
corrupted hash reported as a wrong password), whose FAILs are genuine product defects. Each FAIL is analysed
with the fault label, test name and fault notes hidden, so only the requirement and the evidence remain.
Together with experiments.ai_quality (where every FAIL is a test problem) this measures both directions.

Usage:  .venv\\Scripts\\python.exe -m experiments.triage_faults [--reps 1]
Makes one OpenAI API call per FAIL and repetition. data/qa.db is never touched.
"""

import argparse
import json
import os
import tempfile
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = Path(tempfile.mkdtemp(prefix='triage-faults-'))
os.environ['QA_DB_PATH'] = str(WORK / 'qa.db')

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / '.env')

from qa_system import failure_analysis  # noqa: E402
from qa_system.projects import cases  # noqa: E402
from qa_system.runner import run_suite  # noqa: E402
from scripts.setup_fault_projects import install  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--reps', type=int, default=1, help='같은 실패를 몇 번 분석할지')
    parser.add_argument('--out', default=str(ROOT / 'experiments/results'))
    args = parser.parse_args()
    if not os.getenv('OPENAI_API_KEY'):
        raise SystemExit('.env에 OPENAI_API_KEY가 필요합니다.')
    started = datetime.now(timezone(timedelta(hours=9)))
    projects = install()
    rows = []
    for project_id, case_ids in projects.items():
        faults = [c['id'] for c in cases(project_id) if c['id'] in case_ids]
        run_id = run_suite(faults, project_id=project_id)
        print('run', run_id, flush=True)
        for bug in failure_analysis.failures(run_id):
            facts = json.loads(bug['facts'])
            for rep in range(args.reps):
                try:
                    result = failure_analysis.analyze_failure(bug, blind=True)
                except Exception as error:
                    result = {'likely_cause': None, 'confidence': None, 'suggested_action': type(error).__name__}
                rows.append(
                    dict(
                        test=facts['expected'].get('description'),
                        fault=facts['expected'].get('fault_variant'),
                        rep=rep,
                        run_id=run_id,
                        **{k: result[k] for k in ('likely_cause', 'confidence', 'suggested_action')},
                    )
                )
                print(' ', rows[-1]['fault'], rows[-1]['likely_cause'], flush=True)
    counts = Counter(r['likely_cause'] for r in rows)
    correct = counts['product_defect']
    lines = [
        '# AI 실패 분석 — 실제 제품 결함 인식 확인',
        '',
        f'- 실행: {started.strftime("%Y-%m-%d %H:%M")} (한국 시간) · 모델: `{os.getenv("OPENAI_MODEL", "gpt-4.1-mini")}` · 반복: {args.reps}회',
        '- 대상: 로그인 데모에 의도적으로 넣은 결함 버전. 모든 FAIL의 정답은 **제품 결함**입니다.',
        '- 분석에는 결함 표시, 테스트 이름, 결함 설명을 가리고 요구사항과 실행 증거만 전달했습니다.',
        '',
        '| 분류 | 건수 |',
        '|---|---|',
    ]
    lines += [
        f'| {failure_analysis.CAUSE_LABELS.get(cause, "분석 실패")} | {counts[cause]} |'
        for cause in [*failure_analysis.CAUSE_LABELS, None]
        if counts[cause]
    ]
    lines += [
        '',
        f'정답(제품 결함) 비율: {correct}/{len(rows)}' + (f' ({100 * correct / len(rows):.1f}%)' if rows else ''),
        '',
        '| 주입한 결함 | AI 분류 | 확신도 | AI 제안 |',
        '|---|---|---|---|',
    ]
    lines += [
        f'| {r["fault"]} | {failure_analysis.CAUSE_LABELS.get(r["likely_cause"], "분석 실패")} | '
        f'{failure_analysis.CONFIDENCE_LABELS.get(r["confidence"], "—")} | {" ".join(r["suggested_action"].split()).replace("|", "/")} |'
        for r in rows
    ]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = out / ('triage-faults-' + started.strftime('%Y%m%d-%H%M'))
    stem.with_suffix('.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    stem.with_suffix('.json').write_text(
        json.dumps(dict(rows=rows, counts=dict(counts)), ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print('\n'.join(lines))
    print('결과:', stem.with_suffix('.md'))


if __name__ == '__main__':
    main()
