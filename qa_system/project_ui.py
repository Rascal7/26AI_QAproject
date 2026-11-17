import html
import json
import os
from datetime import datetime, timedelta, timezone
import streamlit as st
from demo_web.db import ROOT
from qa_system import storage
from qa_system.projects import (
    create_project,
    save_project,
    requirements,
    save_requirement,
    cases,
    save_case,
    approve_case,
)
from qa_system.catalog import CASES
from qa_system.web_tests import template_cases
from qa_system.ai import generate_project_cases, canonical_code
from qa_system import failure_analysis
from qa_system.page_context import (
    PageContextError,
    capture,
    check_selectors,
    readable_paths,
    step_selectors,
    summarize_check,
)
from qa_system.runner import run_suite
from qa_system.ui import display_results, run_picker, local_time, VARIANTS, expected_text
from qa_system.workspace import project_list, run_list, all_tags, run_date

ACTION_LABELS = {
    'navigate': '페이지 이동',
    'assert_status': 'HTTP 확인',
    'assert_visible': '요소 표시 확인',
    'assert_text': '문구 확인',
    'assert_url': '주소 확인',
    'fill': '값 입력',
    'click': '클릭',
    'press': '키 입력',
}


def open_project(project_id=None, view='요구사항', requirement_id=None):
    st.session_state.project_id = project_id
    st.session_state.project_view = view
    if requirement_id:
        st.session_state[f'req_filter_{project_id}'] = requirement_id


def open_workspace(view='홈'):
    st.session_state.project_id = None
    st.session_state.workspace_view = view


def close_project_delete():
    st.session_state.pop('delete_project_pending', None)


@st.dialog('프로젝트 삭제', on_dismiss=close_project_delete)
def delete_project_dialog(project):
    from qa_system.projects import delete_project

    st.write(f"'{project['name']}' 프로젝트를 삭제할까요?")
    st.warning('요구사항, 등록된 테스트, 실행 기록과 보고서가 목록에서 영구 삭제됩니다. 되돌릴 수 없습니다.')
    st.caption('로컬 artifacts 폴더의 스크린샷·추적 파일과 백업은 보관됩니다.')
    if project['id'] == storage.baseline_project_id():
        st.info(
            '기본 로그인 데모의 기준 테스트 10개도 삭제됩니다. 필요하면 python -m qa_system.runner --restore-demo 로 다시 만들 수 있습니다.'
        )
    cancel, confirm = st.columns(2)
    if cancel.button('취소', key='cancel_delete_project', width='stretch'):
        close_project_delete()
        st.rerun()
    if confirm.button('삭제', key='confirm_delete_project', type='primary', width='stretch'):
        try:
            delete_project(project['id'])
        except ValueError as error:
            st.error(str(error))
            return
        st.session_state.pop('case_modal', None)
        close_project_delete()
        open_workspace('프로젝트')
        st.rerun()


def tag_chips(tags):
    return (
        '<div class="qa-tags">' + ''.join('<span class="qa-tag">' + html.escape(t) + '</span>' for t in tags) + '</div>'
    )


def status_badges(counts):
    return (
        '<div class="qa-badges">'
        + ''.join(
            f'<span class="qa-status {outcome.lower() if counts.get(outcome, 0) else ""}">{outcome} {int(counts.get(outcome, 0))}</span>'
            for outcome in ('PASS', 'FAIL', 'ERROR')
        )
        + '</div>'
    )


def requirement_text(req):
    try:
        value = json.loads(req['spec'])
        if isinstance(value, dict):
            return value.get('description', '') + '\n' + '\n'.join(value.get('steps', []))
    except (ValueError, TypeError):
        pass
    return req['spec']


@st.dialog('새 프로젝트', width='large')
def new_project_dialog():
    with st.form('new_project_form'):
        name = st.text_input('프로젝트 이름', placeholder='예: 쇼핑몰 주문 페이지')
        url = st.text_input('검사할 웹페이지 URL', placeholder='https://example.com/checkout')
        overview = st.text_area('전체 요구사항', placeholder='이 페이지가 해야 하는 일')
        exceptions = st.text_area('전체 예외사항', placeholder='빈 입력, 접근 제한, 오류 상황 등')
        tags = st.text_input(
            '태그', placeholder='예: 로그인, 쇼핑몰, 회귀 테스트', help='쉼표로 구분해 여러 태그를 입력하세요.'
        )
        if st.form_submit_button('프로젝트 만들기', type='primary', width='stretch'):
            try:
                pid = create_project(name, url, overview, exceptions, tags=tags)
                open_project(pid)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))


@st.dialog('요구사항 추가', width='large')
def new_requirement_dialog(project_id):
    with st.form('new_requirement_form'):
        title = st.text_input('이름', placeholder='예: 이메일 로그인')
        spec = st.text_area('기대 동작', placeholder='정상 입력 시 홈 화면으로 이동한다.')
        exceptions = st.text_area('예외사항', placeholder='잘못된 비밀번호는 오류 문구를 표시한다.')
        if st.form_submit_button('요구사항 추가', type='primary'):
            try:
                save_requirement(project_id, title, spec, exceptions)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))


def dashboard(collection=False):
    all_projects = project_list()
    executions = run_list()
    head, button = st.columns([5, 1.3], vertical_alignment='center')
    with head:
        st.caption('QA AUTOMATION WORKSPACE' if collection else 'WORKSPACE TELEMETRY')
        st.title('프로젝트 목록' if collection else 'QA 워크스페이스')
        st.write(
            '대상 웹페이지와 테스트 상태를 확인하세요.'
            if collection
            else '프로젝트를 생성하고 요구사항 기반 테스트를 실행하세요.'
        )
    with button:
        if st.button('＋ 새 프로젝트', type='primary', width='stretch'):
            new_project_dialog()
    if not collection:
        today = datetime.now(timezone(timedelta(hours=9))).date()
        totals = run_totals(executions)
        daily = run_totals([r for r in executions if run_date(r['started_at']) == today])
        icons = json.loads((ROOT / 'qa_system/testpilot_metric_icons.json').read_text(encoding='utf-8'))
        tested = sum(bool(p['last_run']) for p in all_projects)
        tiles = [
            (
                '활성 프로젝트 수',
                len(all_projects),
                'folder_copy',
                f'{tested}개 프로젝트 실행 이력',
                100 * tested / max(1, len(all_projects)),
                '#0051d5',
            ),
            (
                '오늘 실행된 테스트',
                daily['total'],
                'bolt',
                f'통과 {daily["passed"]}건 · 한국 시간 기준',
                daily['pct'],
                '#009668',
            ),
            (
                '전체 성공률',
                totals['rate'],
                'verified',
                f'통과 {totals["passed"]} / 전체 {totals["total"]}',
                totals['pct'],
                '#009668',
            ),
        ]
        st.markdown(
            '<div class="pilot-metrics">'
            + ''.join(
                f'<article><header>{label}<span>{icons[icon]}</span></header><strong>{value}</strong><small>{detail}</small><div class="pilot-track"><i style="width:{pct}%;background:{color}"></i></div></article>'
                for label, value, icon, detail, pct, color in tiles
            )
            + '</div>',
            unsafe_allow_html=True,
        )
    if collection:
        with st.container(border=True):
            search_col, filter_col = st.columns([2, 1])
            search = search_col.text_input('프로젝트 검색', placeholder='이름 또는 URL', key='project_search')
            tags = filter_col.multiselect(
                '태그', all_tags(), help='선택한 태그 중 하나라도 포함한 프로젝트를 표시합니다.'
            )
        visible = project_list(search, tags)
        st.caption(f'{len(visible)}개 프로젝트 · 최근 실행순 · 미실행 프로젝트는 뒤에 표시')
        visible = paginate(visible, 'projects', (search, tuple(tags)))
    else:
        left, right = st.columns([5, 1])
        left.subheader('최근 프로젝트')
        right.button('더보기 →', key='more_projects', on_click=open_workspace, args=('프로젝트',))
        visible = project_list()[:4]
    if not visible:
        st.info('표시할 프로젝트가 없습니다.')
    latest_by_project = {}
    for run in executions:
        latest_by_project.setdefault(run['project_id'], run)
    columns = 3 if collection else 4
    for offset in range(0, len(visible), columns):
        for col, project in zip(st.columns(columns), visible[offset : offset + columns]):
            with col, st.container(border=True, key=f'project_card_{project["id"]}'):
                last = latest_by_project.get(project['id'])
                label = run_state(last) if last else '미실행'
                stamp = local_time(last['started_at']) if last else ''
                st.markdown(
                    f'<div class="pilot-card-top"><span class="pilot-state state-{state_class(label)}">● {label}</span><time>{stamp}</time></div><div class="project-heading"><h3>'
                    + html.escape(project['name'])
                    + '</h3></div><div class="project-url">'
                    + html.escape(project['target_url'])
                    + '</div>'
                    + tag_chips(json.loads(project['tags'])),
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div class="card-stats"><b>{project["req_count"]}</b> 요구사항 <span>·</span> <b>{project["case_count"]}</b> 테스트</div>',
                    unsafe_allow_html=True,
                )
                result = run_totals([last] if last else [])
                st.markdown(
                    f'<div class="pilot-pass"><span>통과율 <b>{result["rate"]}</b></span><span>{result["passed"]} / {result["total"]} 통과</span></div><div class="pilot-track"><i style="width:{result["pct"]}%"></i></div>',
                    unsafe_allow_html=True,
                )
                actions = st.columns(2)
                actions[0].button(
                    '상세 보기',
                    key=f'open_{project["id"]}',
                    width='stretch',
                    on_click=open_project,
                    args=(project['id'],),
                )
                actions[1].button(
                    '실행 설정',
                    key=f'launch_{project["id"]}',
                    type='primary',
                    width='stretch',
                    on_click=open_project,
                    args=(project['id'], '실행'),
                )
    if collection:
        return
    st.write('')
    left, right = st.columns([5, 1])
    left.subheader('최근 실행 기록')
    right.button('더보기 →', key='more_runs', on_click=open_workspace, args=('실행 기록',))
    render_runs(executions[:5])


def run_totals(runs):
    passed = sum(r['passed'] for r in runs)
    total = sum(r['passed'] + r['failed'] + r['errors'] for r in runs)
    pct = round(100 * passed / total, 1) if total else 0
    return dict(passed=passed, total=total, pct=pct, rate=f'{pct:g}%' if total else '—')


def run_state(run):
    if run['status'] == 'RUNNING':
        return '실행 중'
    if run['status'] == 'ERROR' or run['errors']:
        return '오류'
    if run['failed']:
        return '실패'
    return '통과' if run['passed'] else '결과 없음'


def state_class(label):
    return {'실행 중': 'running', '오류': 'error', '실패': 'fail', '통과': 'pass'}.get(label, 'idle')


def paginate(items, key, filters):
    signature = repr(filters)
    if st.session_state.get(key + '_filters') != signature:
        st.session_state[key + '_filters'] = signature
        st.session_state[key + '_page'] = 1
    pages = max(1, (len(items) + 19) // 20)
    if st.session_state.get(key + '_page', 1) > pages:
        st.session_state[key + '_page'] = 1
    if pages == 1:
        return items
    page = st.selectbox('페이지', list(range(1, pages + 1)), key=key + '_page', format_func=lambda p: f'{p} / {pages}')
    return items[(page - 1) * 20 : page * 20]


def workspace_history():
    st.caption('워크스페이스  /  실행 파이프라인 기록')
    st.title('전체 실행 기록')
    st.caption('전체 프로젝트의 실행 기록 · 현재 프로젝트 태그 기준 · 날짜는 한국 시간')
    metrics_area = st.container()
    search_col, tag_col, state_col = st.columns([2, 1.5, 1])
    search = search_col.text_input('프로젝트 또는 실행 ID', placeholder='실행 기록 검색')
    tags = tag_col.multiselect('태그', all_tags(), help='선택한 태그 중 하나라도 포함한 프로젝트의 기록을 표시합니다.')
    status = state_col.selectbox('실행 상태', ['전체', '통과', '실패', '오류', '실행 중'])
    start = end = None
    if st.checkbox('날짜로 필터'):
        left, right = st.columns(2)
        start = left.date_input('시작일')
        end = right.date_input('종료일')
        if start > end:
            st.error('종료일은 시작일 이후여야 합니다.')
            return
    runs = [
        r
        for r in run_list(tags, start, end)
        if search.casefold() in (r['name'] + ' ' + r['run_id']).casefold()
        and (status == '전체' or status == run_state(r))
    ]
    durations = [
        (datetime.fromisoformat(r['finished_at']) - datetime.fromisoformat(r['started_at'])).total_seconds()
        for r in runs
        if r['finished_at']
    ]
    metrics = metrics_area.columns(4)
    for col, (label, value) in zip(
        metrics,
        [
            ('기간 내 총 실행', len(runs)),
            ('전체 통과율', run_totals(runs)['rate']),
            ('평균 소요 시간', f'{sum(durations) / len(durations):.1f}초' if durations else '—'),
            ('실패 테스트', sum(r['failed'] for r in runs)),
        ],
    ):
        col.metric(label, value, border=True)
    st.caption(f'{len(runs)}개 실행 · 최신순')
    render_runs(paginate(runs, 'workspace_runs', (tuple(tags), start, end, search, status)))


def render_runs(recent):
    if not recent:
        st.info('표시할 실행 기록이 없습니다.')
        return
    with st.container(key='run_table'):
        widths = [1, 1.2, 2.5, 1.6, 2.1, 1.1]
        for col, label in zip(
            st.columns(widths), ['상태', '실행 ID', '프로젝트 / 대상 URL', '실행 일시', '결과 지표', '리포트']
        ):
            col.markdown('<div class="qa-table-label">' + label + '</div>', unsafe_allow_html=True)
        for run in recent:
            with st.container(key='run_row_' + run['run_id']):
                s, i, a, b, r, c = st.columns(widths, vertical_alignment='center')
                state = run_state(run)
                s.markdown(
                    f'<span class="pilot-state state-{state_class(state)}">● {state}</span>', unsafe_allow_html=True
                )
                i.caption('#' + run['run_id'][:8])
                a.markdown(
                    '<div class="qa-run-name">'
                    + html.escape(run['name'])
                    + '</div><div class="pilot-url">'
                    + html.escape(run['target_url'])
                    + '</div>'
                    + tag_chips(json.loads(run['tags'])),
                    unsafe_allow_html=True,
                )
                b.markdown(
                    '<div class="qa-run-date">'
                    + str(run_date(run['started_at']).year)
                    + '년 '
                    + local_time(run['started_at'])
                    + '</div>',
                    unsafe_allow_html=True,
                )
                r.markdown(
                    status_badges({'PASS': run['passed'], 'FAIL': run['failed'], 'ERROR': run['errors']}),
                    unsafe_allow_html=True,
                )
                c.button(
                    '기록 보기',
                    key='recent_' + run['run_id'],
                    on_click=open_history,
                    args=(run['project_id'], run['run_id']),
                )


def open_history(project_id, run_id):
    open_project(project_id, '실행 기록')
    st.session_state[f'selected_run_{project_id}'] = run_id


def requirements_page(project):
    pid = project['id']
    st.subheader('페이지 기본 규칙 및 예외 처리')
    rule, exception = st.columns(2)
    for col, label, value in [
        (rule, '기본 요구사항', project['overview']),
        (exception, '예외 처리', project['exceptions']),
    ]:
        col.markdown(
            '<div class="pilot-policy"><b>'
            + label
            + '</b><p>'
            + html.escape(value or '작성된 내용이 없습니다.')
            + '</p></div>',
            unsafe_allow_html=True,
        )
    with st.expander('전체 기준 수정'):
        with st.form(f'overview_{pid}'):
            left, right = st.columns(2)
            overview = left.text_area(
                '전체 요구사항', project['overview'], placeholder='프로젝트 전체의 기대 동작', height=130
            )
            exceptions = right.text_area(
                '전체 예외사항', project['exceptions'], placeholder='모든 테스트에서 확인할 예외', height=130
            )
            if st.form_submit_button('전체 기준 저장', type='primary'):
                save_project(pid, project['name'], overview, exceptions)
                st.success('저장했습니다.')
    a, b = st.columns([4, 1])
    a.subheader('개별 요구사항별 테스트 그룹')
    if b.button('＋ 추가', width='stretch'):
        new_requirement_dialog(pid)
    reqs = requirements(pid)
    if not reqs:
        st.info('요구사항을 추가하세요. 요구사항마다 테스트를 연결할 수 있습니다.')
        return
    grouped = {}
    for case in cases(pid):
        grouped.setdefault(case['requirement_id'], []).append(case)
    latest_results = storage.rows(
        'SELECT r.case_id,r.outcome FROM test_results r JOIN test_runs h ON h.run_id=r.run_id WHERE h.project_id=? ORDER BY h.started_at, r.id',
        (pid,),
    )
    outcomes = {r['case_id']: r['outcome'] for r in latest_results}
    for req in reqs:
        with st.container(border=True):
            a, b = st.columns([5, 1.2], vertical_alignment='center')
            a.subheader(req['title'] or req['id'])
            a.caption(requirement_text(req).split('\n')[0])
            group = grouped.get(req['id'], [])
            b.button(
                f'테스트 {len(group)}개 →',
                key='to_tests_' + req['id'],
                width='stretch',
                on_click=open_project,
                args=(pid, '테스트', req['id']),
            )
            if group:
                with st.expander('테스트 케이스 · 실행 결과', expanded=req['id'] == reqs[0]['id']):
                    st.dataframe(
                        [
                            {
                                '테스트 ID': c['id'],
                                '검사 항목': c['description'],
                                '최근 결과': outcomes.get(c['id'], '미실행'),
                            }
                            for c in group
                        ],
                        hide_index=True,
                        width='stretch',
                    )
            with st.expander('내용 수정'):
                with st.form('req_edit_' + req['id']):
                    title = st.text_input('이름', req['title'])
                    spec = st.text_area('기대 동작', requirement_text(req))
                    exc = st.text_area('예외사항', req['exceptions'])
                    if st.form_submit_button('저장'):
                        try:
                            save_requirement(pid, title, spec, exc, req['id'])
                            st.rerun()
                        except ValueError as error:
                            st.error(str(error))


def step_editor(steps, key):
    display = [
        {
            '동작': ACTION_LABELS.get(s['action'], s['action']),
            '요소 선택자': s.get('selector', ''),
            '값 / 경로': s.get('value', ''),
        }
        for s in steps
    ]
    edited = st.data_editor(
        display,
        num_rows='dynamic',
        hide_index=True,
        width='stretch',
        key=key,
        column_config={
            '동작': st.column_config.SelectboxColumn(options=list(ACTION_LABELS.values()), required=True),
            '요소 선택자': st.column_config.TextColumn(help='예: h1, #email, button[type=submit]'),
            '값 / 경로': st.column_config.TextColumn(help='기대 문구, 입력값, 이동 경로'),
        },
    )
    reverse = {v: k for k, v in ACTION_LABELS.items()}
    return [
        {
            'action': reverse.get(r.get('동작'), ''),
            'selector': r.get('요소 선택자') or '',
            'value': r.get('값 / 경로') or '',
        }
        for r in edited
    ]


def page_summary(context):
    """'/welcome, /home(로그인 필요 → /login)' style list of the other pages that were looked at."""
    parts = []
    for page in (context or {}).get('other_pages', []):
        if page.get('error'):
            parts.append(f'{page["path"]}(열지 못함)')
        elif page.get('redirected_to') and page.get('elements') is None:
            parts.append(f'{page["path"]}(접근 제한 → {page["redirected_to"]})')
        else:
            parts.append(page['path'])
    return ', '.join(parts)


def selector_check_view(project, draft, steps, key, paths=()):
    """Show whether each selector exists on the pages that were read; editing steps invalidates the result."""
    check = draft.get('selector_check')
    if check and check.get('selectors') != step_selectors(steps):
        check = None  # The reviewer edited selectors after the last check.
    if check:
        elsewhere = check.get('elsewhere', {})
        message = f'선택자 {check["total"]}개 중 {check["unique"]}개를 시작 페이지에서'
        if elsewhere:
            message += f', {len(elsewhere)}개를 이동 후 페이지({", ".join(sorted(set(elsewhere.values())))})에서'
        message += ' 정확히 1개로 확인했습니다.'
        problems = [
            ('찾지 못함', check['missing']),
            ('여러 요소와 일치', check['multiple']),
            ('문법 오류', check['invalid']),
        ]
        details = ' · '.join(f'{label}: {", ".join(values)}' for label, values in problems if values)
        if details:
            st.warning(
                message + ' ' + details + ' (읽지 못한 페이지·로그인이 필요한 페이지의 요소라면 직접 확인하세요.)'
            )
        else:
            st.success(message)
    if step_selectors(steps) and st.button('선택자 다시 확인', key='recheck_' + key):
        try:
            with st.spinner('실제 페이지에서 확인하고 있습니다…'):
                draft['selector_check'] = summarize_check(
                    steps, check_selectors(project['target_url'], step_selectors(steps), paths)
                )
            st.rerun()
        except PageContextError as error:
            st.error(str(error))


def tests_page(project):
    pid = project['id']
    reqs = requirements(pid)
    notice = st.session_state.pop(f'tests_added_{pid}', None)
    if notice:
        st.success(notice)
    if not reqs:
        st.info('먼저 요구사항을 추가하세요.')
        st.button('요구사항 추가', on_click=open_project, args=(pid, '요구사항'))
        return
    options = {r['id']: r for r in reqs}
    key = f'req_filter_{pid}'
    if st.session_state.get(key) not in options:
        st.session_state[key] = next(iter(options))
    rid = st.selectbox('요구사항', list(options), format_func=lambda k: options[k]['title'] or k, key=key)
    req = options[rid]
    title, action = st.columns([3, 1], vertical_alignment='center')
    title.subheader('등록된 테스트')
    if action.button('＋ 테스트 추가', key='show_test_modal', type='primary', width='stretch'):
        st.session_state.case_modal = (pid, rid)
    if st.session_state.get('case_modal') == (pid, rid):
        case_adder(project, req)
    with st.container():
        current = cases(pid, rid)
        if not current:
            st.info('아직 테스트가 없습니다. 기본 테스트를 선택하거나 AI에게 요청하세요.')
        for case in current:
            with st.expander(case['description'] + '  ·  ' + ('실행 가능' if case['reviewed'] else '검토 필요')):
                if case.get('fault_variant'):
                    st.warning('의도적 결함 재현 · 실행 시 자동 적용: ' + VARIANTS[case['fault_variant']])
                st.write(expected_text(case))
                if case.get('engine') == 'web':
                    st.dataframe(
                        [
                            {
                                '순서': i + 1,
                                '동작': ACTION_LABELS[s['action']],
                                '대상': s.get('selector', ''),
                                '값': s.get('value', ''),
                            }
                            for i, s in enumerate(case['steps'])
                        ],
                        hide_index=True,
                        width='stretch',
                    )
                else:
                    st.caption('데모 기준 테스트 · ' + case.get('baseline_id', case['id']))
                    if case.get('source') == 'ai':
                        st.caption('초기 버전 AI 테스트 · 아래 고정 실행 코드로만 실행됩니다.')
                        st.code(canonical_code(case.get('baseline_id', case['id'])), language='python')
                if not case['reviewed'] and st.button('검토 완료 · 승인', key='approve_' + case['id']):
                    approve_case(pid, case['id'])
                    st.rerun()
        if current:
            st.button('실행하러 가기 →', type='primary', on_click=open_project, args=(pid, '실행', rid))


def close_case_adder():
    st.session_state.pop('case_modal', None)


@st.dialog('테스트 추가', width='large', on_dismiss=close_case_adder)
def case_adder(project, req):
    pid, rid = project['id'], req['id']
    st.caption(project['name'] + '  /  ' + req['title'])
    basic_panel, ai_panel = st.columns(2, gap='medium')
    with basic_panel, st.container(border=True):
        st.subheader('기본 테스트 케이스')
        templates = template_cases()
        if project['mode'] == 'demo':
            category = st.radio('테스트 종류', ['로그인·DB 기준', '웹 공통'], horizontal=True)
        else:
            category = '웹 공통'
        if category == '로그인·DB 기준':
            selected = st.multiselect('추가할 기본 테스트', list(CASES), format_func=lambda k: CASES[k]['description'])
            if st.button('선택한 테스트 추가', type='primary', disabled=not selected):
                for baseline in selected:
                    save_case(pid, rid, dict(CASES[baseline], baseline_id=baseline, engine='demo'), reviewed=True)
                st.session_state[f'tests_added_{pid}'] = (
                    f'{len(selected)}개 테스트를 추가했습니다. 등록된 테스트에서 확인하세요.'
                )
                close_case_adder()
                st.rerun()
        else:
            kind = st.selectbox(
                '기본 테스트',
                list(templates),
                format_func=lambda k: templates[k]['description'] + ' · ' + templates[k]['summary'],
            )
            template = templates[kind]
            title = st.text_input('테스트 이름', template['description'], key=f'title_{pid}_{rid}_{kind}')
            st.caption('선택자와 기대값을 페이지에 맞게 수정하세요. 빈 이동 경로는 프로젝트 URL을 사용합니다.')
            steps = step_editor(template['steps'], f'template_{pid}_{rid}_{kind}')
            if st.button('테스트 추가', type='primary'):
                try:
                    save_case(
                        pid,
                        rid,
                        dict(engine='web', description=title, expected=title, steps=steps, template_id=kind),
                        reviewed=True,
                    )
                    st.session_state[f'tests_added_{pid}'] = '추가했습니다. 등록된 테스트에서 확인하세요.'
                    close_case_adder()
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
    with ai_panel, st.container(border=True):
        st.subheader('AI 테스트 생성')
        prompt = st.text_area(
            '어떤 테스트를 할까요?',
            placeholder='예: 이메일을 비우고 로그인하면 오류 문구가 표시되는지 확인해줘. 이메일은 #email, 버튼은 #submit이야.',
            height=120,
            key=f'prompt_{pid}_{rid}',
        )
        use_page = st.checkbox(
            '페이지 구조를 읽어 AI에 전달',
            value=True,
            key=f'use_page_{pid}_{rid}',
            help='등록한 URL과, 그 페이지의 링크·요구사항에 적힌 같은 사이트 경로(예: /home)를 브라우저로 조회해 '
            '입력창·버튼·링크·안내 영역의 선택자를 AI에 전달합니다. 입력·제출은 하지 않고 입력값도 읽지 않으며, '
            '로그아웃·삭제처럼 상태를 바꿀 수 있는 링크는 열지 않습니다.',
        )
        st.caption('전체 기준과 선택한 요구사항을 함께 전달합니다. 생성 후 검토하세요.')
        draft_key = f'drafts_{pid}_{rid}'
        if st.button('✦ 테스트 생성', type='primary', disabled=not prompt.strip()):
            context, context_error = None, None
            if use_page:
                try:
                    hints = [project['overview'], project['exceptions'], req.get('spec'), req.get('exceptions'), prompt]
                    with st.spinner('페이지 구조를 읽고 있습니다…'):
                        context = capture(project['target_url'], hints)
                except PageContextError as error:
                    context_error = str(error)
            try:
                with st.spinner('테스트를 만들고 있습니다…'):
                    drafts = generate_project_cases(project, req, prompt, context)
                paths = readable_paths(context)
                if context:
                    with st.spinner('생성된 선택자를 실제 페이지에서 확인하고 있습니다…'):
                        counts = check_selectors(
                            project['target_url'], [s for d in drafts for s in step_selectors(d['steps'])], paths
                        )
                    for draft in drafts:
                        draft['selector_check'] = summarize_check(draft['steps'], counts)
                st.session_state[draft_key] = drafts
                st.session_state[draft_key + '_context'] = {
                    'elements': len(context['elements']) if context else 0,
                    'pages': page_summary(context),
                    'paths': paths,
                    'error': context_error,
                }
                st.session_state[draft_key + '_revision'] = st.session_state.get(draft_key + '_revision', 0) + 1
            except PageContextError as error:
                st.error(str(error))
            except Exception as error:
                st.error(f'생성 실패: {type(error).__name__}. API 설정과 연결을 확인하세요.')
        context_info = st.session_state.get(draft_key + '_context')
        if context_info and st.session_state.get(draft_key):
            if context_info['error']:
                st.warning(
                    '페이지 구조 없이 생성했습니다. 선택자가 추정값이므로 꼭 확인하세요. ' + context_info['error']
                )
            else:
                pages = context_info.get('pages')
                st.caption(
                    f'페이지에서 읽은 요소 {context_info["elements"]}개'
                    + (f'와 이동 후 페이지 {pages}' if pages else '')
                    + '를 바탕으로 생성했습니다.'
                )
        for index, draft in enumerate(st.session_state.get(draft_key, [])):
            revision = st.session_state.get(draft_key + '_revision', 0)
            with st.container(border=True):
                st.subheader(draft['description'])
                st.write(draft['expected'])
                if draft.get('review_notes'):
                    st.warning(draft['review_notes'])
                steps = step_editor(draft['steps'], f'ai_steps_{pid}_{rid}_{revision}_{index}')
                selector_check_view(
                    project, draft, steps, f'{pid}_{rid}_{revision}_{index}', (context_info or {}).get('paths', ())
                )
                approved = st.checkbox(
                    '실행 단계와 선택자를 확인했습니다', key=f'ai_approved_{pid}_{rid}_{revision}_{index}'
                )
                saved = bool(draft.get('_saved_case_id'))
                if st.button(
                    '등록 완료' if saved else '프로젝트에 추가',
                    key=f'ai_save_{pid}_{rid}_{revision}_{index}',
                    disabled=saved or not approved,
                ):
                    try:
                        draft['_saved_case_id'] = save_case(pid, rid, dict(draft, steps=steps), reviewed=True)
                        st.session_state[f'tests_added_{pid}'] = (
                            'AI 테스트를 추가했습니다. 등록된 테스트에서 확인하세요.'
                        )
                        close_case_adder()
                        st.rerun()
                    except ValueError as error:
                        st.error(str(error))


def execution_page(project):
    pid = project['id']
    current = cases(pid)
    if not current:
        st.info('실행할 테스트가 없습니다. 요구사항에 테스트를 추가하세요.')
        return
    reqs = {r['id']: r['title'] for r in requirements(pid)}
    left, right = st.columns([2.2, 1], gap='large')
    with left, st.container(border=True):
        scope = st.selectbox(
            '요구사항별 실행', [None, *reqs], format_func=lambda r: '전체 요구사항' if r is None else reqs[r]
        )
        available = [c for c in current if (scope is None or c['requirement_id'] == scope) and c['reviewed']]
        pending = sum(1 for c in current if (scope is None or c['requirement_id'] == scope) and not c['reviewed'])
        if pending:
            st.caption(
                f'검토·승인하지 않은 테스트 {pending}개는 목록에서 제외했습니다. 테스트 추가 화면에서 승인하세요.'
            )
        mapping = {c['id']: c for c in available}
        selected = st.multiselect(
            '실행할 테스트',
            list(mapping),
            default=list(mapping),
            format_func=lambda k: mapping[k]['description'],
            key=f'run_selection_{pid}_{scope}',
        )
        if any(mapping[k].get('fault_variant') for k in selected):
            st.info('결함 재현 테스트는 지정된 결함을 자동 적용합니다. FAIL은 해당 결함을 발견했다는 뜻입니다.')
        variant = 'normal'
        if project['mode'] == 'demo':
            with st.expander('결함 실험'):
                variant = st.selectbox('대상 버전', list(VARIANTS), format_func=VARIANTS.get)
        if project['mode'] == 'web':
            st.caption('등록한 사이트에서 실제로 입력과 클릭을 실행합니다.')
        has_key = bool(os.getenv('OPENAI_API_KEY'))
        auto_analyze = st.checkbox(
            '실패하면 AI 원인 분석 실행',
            value=has_key,
            disabled=not has_key,
            key=f'auto_analyze_{pid}',
            help=f'FAIL 항목마다 실행 증거를 AI에 보내 테스트 문제·제품 결함·환경 문제를 구분합니다. 실행당 최대 {failure_analysis.MAX_PER_RUN}건.'
            + ('' if has_key else ' API 키가 없어 사용할 수 없습니다.'),
        )
    with right, st.container(border=True):
        st.subheader('실행')
        st.metric('선택한 테스트', len(selected))
        st.caption(project['target_url'])
        if st.button('▶ 테스트 실행', type='primary', width='stretch', disabled=not selected):
            try:
                with st.status('테스트 실행 중', expanded=True) as status:
                    bar = st.progress(0.0, text='브라우저를 준비하고 있습니다…')

                    def report_progress(done, total):
                        bar.progress(done / total if total else 1.0, text=f'{done} / {total}개 완료')

                    run_id = run_suite(selected, variant, project_id=pid, progress=report_progress)
                    if auto_analyze and failure_analysis.failures(run_id):
                        status.update(label='실패 항목을 AI로 분석하고 있습니다…')
                        _, errors = failure_analysis.analyze_run(run_id)
                        if errors:
                            st.warning('일부 실패는 AI 분석을 하지 못했습니다: ' + ', '.join(errors))
                    status.update(label='실행 완료', state='complete', expanded=False)
                st.session_state[f'selected_run_{pid}'] = run_id
                st.session_state[f'last_project_run_{pid}'] = run_id
            except Exception as error:
                st.error(str(error))
        if st.session_state.get(f'last_project_run_{pid}'):
            st.button('실행 기록 보기 →', on_click=open_project, args=(pid, '실행 기록'), width='stretch')


def failure_panel(run_id, report):
    bugs = failure_analysis.failures(run_id)
    if not bugs:
        st.info('기록된 동작 불일치(FAIL)가 없습니다. 검증 오류는 검사 결과에서 확인하세요.')
    for bug in bugs:
        with st.expander(bug['title'], expanded=True):
            facts = json.loads(bug['facts'])
            st.write(facts.get('error') or '기대 동작과 실제 동작이 다릅니다.')
            if not bug.get('ai_analysis'):
                st.caption(bug['hypothesis'])
                continue
            a = json.loads(bug['ai_analysis'])
            cause = failure_analysis.CAUSE_LABELS[a['likely_cause']]
            badge = {
                'test_definition': st.warning,
                'product_defect': st.error,
                'environment': st.info,
                'unclear': st.info,
            }[a['likely_cause']]
            confidence = failure_analysis.CONFIDENCE_LABELS[a['confidence']]
            badge(f'AI 분류: **{cause}** · 확신도 {confidence}\n\n{a["suggested_action"]}')
            for key, title in [
                ('observed_facts', '관찰한 사실 (실행 증거)'),
                ('hypotheses', '추정 원인 (AI 판단)'),
                ('suggested_checks', '다음 확인 사항'),
            ]:
                st.markdown(f'**{title}**')
                for item in a.get(key, []):
                    st.write('• ' + item)
    pending = [b for b in bugs if not b.get('ai_analysis')]
    if pending and st.button(
        f'AI 원인 분석 · {len(pending)}건', key=f'analyze_{run_id}', disabled=not os.getenv('OPENAI_API_KEY')
    ):
        with st.spinner('실패 항목을 분석하고 있습니다…'):
            _, errors = failure_analysis.analyze_run(run_id)
        if errors:
            st.error('분석하지 못한 항목: ' + ', '.join(errors) + '. API 설정과 연결을 확인하세요.')
        else:
            st.rerun()
    if report and report['ai_analysis']:
        # Earlier versions stored one report-level analysis; keep showing it for old runs.
        with st.expander('이전 방식의 보고서 전체 AI 분석'):
            parsed = json.loads(report['ai_analysis'])
            for key, title in [
                ('observed_facts', '관찰한 사실'),
                ('hypotheses', '추정 원인'),
                ('suggested_checks', '다음 확인 사항'),
            ]:
                st.markdown(f'**{title}**')
                for item in parsed.get(key, []):
                    st.write('• ' + item)


def history_page(project):
    run_id = run_picker(project['id'])
    if not run_id:
        return
    results_tab, analysis_tab, report_tab = st.tabs(['검사 결과', '실패 분석', '보고서 다운로드'])
    report_rows = storage.rows('SELECT * FROM reports WHERE run_id=?', (run_id,))
    report = report_rows[0] if report_rows else None
    with results_tab:
        display_results(run_id)
    with analysis_tab:
        failure_panel(run_id, report)
    with report_tab:
        if report:
            appendix = failure_analysis.analysis_markdown(run_id)
            full = report['markdown'] + ('\n' + appendix if appendix else '')
            st.download_button('보고서 다운로드 · Markdown', full, file_name=f'QA-{run_id}.md', type='primary')
            with st.expander('보고서 전문'):
                st.markdown(full)
        else:
            st.info('아직 보고서가 생성되지 않았습니다.')
