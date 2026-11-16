import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import streamlit as st
from qa_system.storage import rows

VARIANTS = {
    'normal': '정상 버전',
    'skip_disabled': '비활성 검사 누락',
    'skip_lock': '잠금 검사 누락',
    'skip_revalidation': '삭제 사용자 재검증 누락',
    'misclassify_hash': '손상 데이터 오류 분류 누락',
}


def local_time(value):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone(timedelta(hours=9))).strftime('%m월 %d일 %H:%M')


def expected_text(case):
    if case.get('engine') == 'web':
        return case.get('expected') or case.get('description', '웹 동작 확인')
    return {
        None: '입력 오류 안내 · 요청 없음',
        200: '로그인 성공 · 홈 이동',
        401: '잘못된 자격증명 차단',
        403: '제한된 계정 로그인 차단',
        503: '안전한 오류 안내 · 세션 없음',
        302: '삭제 후 로그인 화면 복귀',
    }.get(case.get('expected_status'), '기술 상세 참조')


def run_picker(project_id=None):
    runs = rows(
        'SELECT run_id,variant,started_at FROM test_runs'
        + (' WHERE project_id=?' if project_id else '')
        + ' ORDER BY started_at DESC',
        (project_id,) if project_id else (),
    )
    if not runs:
        st.info('아직 실행 기록이 없습니다. 테스트를 추가하고 실행하세요.')
        return None
    ids = [r['run_id'] for r in runs]
    labels = {
        r['run_id']: f'{local_time(r["started_at"])} · {VARIANTS.get(r["variant"], r["variant"])} · {r["run_id"][:6]}'
        for r in runs
    }
    key = f'selected_run_{project_id}'
    if st.session_state.get(key) not in ids:
        st.session_state[key] = ids[0]
    return st.selectbox('실행 기록 · 한국 시간', ids, format_func=labels.get, key=key)


def display_results(run_id):
    results = rows('SELECT * FROM test_results WHERE run_id=? ORDER BY id', (run_id,))
    names = {r['id']: json.loads(r['definition'])['description'] for r in rows('SELECT id,definition FROM test_cases')}
    labels = {'PASS': '통과', 'FAIL': '동작 불일치', 'ERROR': '검증 오류'}
    for col, outcome in zip(st.columns(3), labels):
        col.metric(labels[outcome] + ' · ' + outcome, sum(r['outcome'] == outcome for r in results))
    st.caption('예상한 401·403·503 응답도 통과입니다. 검증 오류는 제품 결함과 구분합니다.')
    mode = st.radio('표시할 결과', ['전체', '확인이 필요한 항목'], horizontal=True)
    visible = [r for r in results if mode == '전체' or r['outcome'] != 'PASS']
    if not visible:
        st.success('확인이 필요한 항목이 없습니다.')
        return
    table = []
    for r in visible:
        d = json.loads(r['details'])
        table.append(
            {
                '결과': labels.get(r['outcome'], r['outcome']) + ' · ' + r['outcome'],
                '검사 항목': names.get(r['case_id'], r['case_id']),
                '기대 동작': expected_text(d.get('expected', {})),
                '실제 HTTP': ' → '.join(str(x['status']) for x in d.get('http', [])) or '요청 없음',
                '준비': {'ready': '완료', 'failed': '실패', 'pending': '대기'}.get(
                    r['setup_status'], r['setup_status']
                ),
            }
        )
    st.dataframe(table, hide_index=True, width='stretch')
    st.subheader('항목별 증거')
    for r in visible:
        with st.expander(r['outcome'] + ' · ' + names.get(r['case_id'], r['case_id'])):
            detail = json.loads(r['details'])
            st.caption(r['case_id'])
            if detail.get('error'):
                st.error(detail['error'])
            for observation in detail.get('observations', []):
                st.write('• ' + observation)
            evidence = detail.get('evidence', {})
            if evidence.get('screenshot') and Path(evidence['screenshot']).exists():
                st.image(evidence['screenshot'], width=600)
            if evidence.get('trace') and Path(evidence['trace']).exists():
                st.download_button(
                    '브라우저 기록 다운로드',
                    Path(evidence['trace']).read_bytes(),
                    file_name=r['case_id'] + '.trace.zip',
                    key=f'trace_{r["id"]}',
                )
            with st.expander('기술 상세 · HTTP / 세션 / DB'):
                st.json(detail)
