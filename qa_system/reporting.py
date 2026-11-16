from collections import Counter
from qa_system.catalog import SCENARIOS
from qa_system.storage import rows


def build_report(run_id):
    import json
    run = rows('SELECT * FROM test_runs WHERE run_id=?', (run_id,))[0]
    results = rows('SELECT * FROM test_results WHERE run_id=? ORDER BY id', (run_id,))
    project = rows('SELECT * FROM projects WHERE id=?', (run['project_id'],))[0]
    snapshots = json.loads(run['snapshots'])
    saved_project = snapshots.get('project', project)
    web_run = any(json.loads(r['details']).get('engine') == 'web' for r in results)
    counts = Counter(r['outcome'] for r in results)
    coverage = {r['scenario_id'] for r in results if r['scenario_id'] and r['setup_status'] == 'ready' and r['outcome'] in ('PASS', 'FAIL')}
    lines = ['# 웹 QA 실행 보고서', '', f"프로젝트: {saved_project['name']} · 대상: {run['target_url']}",
             f"전체 요구사항: {saved_project.get('overview','')}", f"전체 예외사항: {saved_project.get('exceptions','')}",
             f"실행: {run_id} · 버전: {run['variant']} · 시드: {run['seed_version']}",
             f"시작: {run['started_at']} · 종료: {run['finished_at']}", '',
             f"PASS {counts['PASS']} / FAIL {counts['FAIL']} / ERROR {counts['ERROR']}",
             (f'유효 DB 시나리오 커버리지: {len(coverage)}/{len(SCENARIOS)} ({100*len(coverage)/len(SCENARIOS):g}%)' if project['mode']=='demo' else '웹 요구사항별 브라우저 검증'),
             f"실행 완료율: {counts['PASS'] + counts['FAIL']}/{len(results)} (PASS·FAIL 판정까지 끝난 테스트, ERROR 제외)",
             'ERROR는 커버리지·결함 발견 집계에서 제외합니다. 기대된 401·403·503은 정상 처리입니다.', '']
    for group, title in ((False, '웹 테스트' if web_run else '기본 로그인'), (True, 'DB 시나리오')):
        if not any(bool(r['scenario_id'])==group for r in results):
            continue
        lines += [f'## {title}', '', '| 테스트 | 시나리오 | 준비 | 판정 | HTTP |', '|---|---|---|---|---|']
        for r in results:
            if bool(r['scenario_id']) != group:
                continue
            d = json.loads(r['details'])
            http = ', '.join(str(h['status']) for h in d.get('http', [])) or '요청 없음'
            lines.append(f"| {r['case_id']} | {r['scenario_id'] or '-'} | {r['setup_status']} | {r['outcome']} | {http} |")
        lines.append('')
    for r in results:
        d = json.loads(r['details'])
        lines += [f"## {r['case_id']} — {r['outcome']}", '',
            f"대상 버전: {d.get('target_variant', run['variant'])}" + (' (의도적 결함 재현)' if d.get('expected', {}).get('fault_variant') else ''),
            ('재현 단계: '+json.dumps(d.get('steps',[]),ensure_ascii=False) if d.get('engine')=='web'
             else '재현: 새 시드 → 지정 시점의 고정 DB fixture → 로그인 제출 → HTTP·화면·세션·DB 확인.'),
            f"시나리오 버전: {snapshots.get('scenarios', {}).get(r['scenario_id'], {}).get('version', '-') if r['scenario_id'] else '-'} / 준비: {r['setup_status']}",
            f"기대: {json.dumps(d.get('expected', {}), ensure_ascii=False)}",
            f"변경 전: {json.dumps(d.get('before'), ensure_ascii=False)}",
            f"변경 후: {json.dumps(d.get('after'), ensure_ascii=False)}",
            f"관찰: {json.dumps(d.get('http', []), ensure_ascii=False)}",
            f"화면 및 검증: {'; '.join(d.get('observations', []))}",
            f"세션: {d.get('session', '검사 항목 아님' if d.get('engine')=='web' else '검증 완료 전 중단')}",
            f"오류: {d.get('error') or '없음'}",
            f"증거: {json.dumps(d.get('evidence', {}), ensure_ascii=False)}", '']
    return '\n'.join(lines)
