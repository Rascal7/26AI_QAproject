import html
import json
import os
from collections import Counter
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
from qa_system import background
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


ICONS = json.loads((ROOT / 'qa_system/testpilot_metric_icons.json').read_text(encoding='utf-8'))
PROJECT_PAGE_SIZE = 6
PROJECT_SORTS = ['최근 실행순', '이름순', '통과율 낮은순']
RUN_STATES = ['전체', '통과', '실패', '오류', '실행 중']


def run_seconds(run):
    if not run or not run.get('finished_at') or not run.get('started_at'):
        return None
    return (datetime.fromisoformat(run['finished_at']) - datetime.fromisoformat(run['started_at'])).total_seconds()


def format_duration(seconds):
    if seconds is None:
        return '—'
    seconds = round(seconds)
    return f'{seconds // 60}분 {seconds % 60:02d}초' if seconds >= 60 else f'{seconds}초'


def short_id(case_id):
    """TC-LOGIN-001 stays as is; long generated ids such as CASE-1a2b3c4d5e6f become CASE-…4d5e6f."""
    return case_id if len(case_id) <= 14 else f'{case_id[:5]}…{case_id[-6:]}'


def safe_link(url):
    """Only http(s) addresses become links; anything else is shown as text."""
    return html.escape(url) if url.startswith(('http://', 'https://')) else ''


def metric_tiles(tiles, columns=3):
    """Telemetry tiles: (label, value, icon, detail, bar percent or None, bar color, tone)."""
    cells = []
    for label, value, icon, detail, pct, color, tone in tiles:
        bar = (
            f'<div class="pilot-track"><i style="width:{pct}%;background:{color}"></i></div>' if pct is not None else ''
        )
        cells.append(
            f'<article class="{tone}"><header>{label}<span>{ICONS[icon]}</span></header>'
            f'<strong>{value}</strong><small>{detail}</small>{bar}</article>'
        )
    st.markdown(f'<div class="pilot-metrics cols-{columns}">' + ''.join(cells) + '</div>', unsafe_allow_html=True)


def section_header(title, badge, more_label=None, more_key=None, target=None):
    left, right = st.columns([5, 1.6], vertical_alignment='center')
    left.markdown(f'<div class="pilot-section"><strong>{title}</strong><em>{badge}</em></div>', unsafe_allow_html=True)
    if more_label:
        right.button(more_label, key=more_key, on_click=open_workspace, args=(target,))


def quick_run(project_id):
    """Start every approved test of the project in the background and show its run page."""
    approved = [c['id'] for c in cases(project_id) if c['reviewed']]
    open_project(project_id, '실행')
    if not approved:
        st.session_state[f'run_notice_{project_id}'] = '실행할 승인된 테스트가 없습니다. 테스트를 추가하고 승인하세요.'
        return
    try:
        st.session_state[f'run_job_{project_id}'] = background.start(
            project_id, approved, analyze=bool(os.getenv('OPENAI_API_KEY'))
        )
    except ValueError as error:
        st.session_state[f'run_notice_{project_id}'] = str(error)


def open_add_test(project_id, requirement_id=None):
    """Open the add-test dialog for a requirement (the selected one, else the first)."""
    reqs = requirements(project_id)
    if not reqs:
        open_project(project_id, '요구사항')
        return
    ids = [r['id'] for r in reqs]
    rid = requirement_id or st.session_state.get(f'req_filter_{project_id}')
    rid = rid if rid in ids else ids[0]
    open_project(project_id, '테스트', rid)
    st.session_state.case_modal = (project_id, rid)


def card_state(run):
    if not run:
        return '미실행', 'idle'
    if run['status'] == 'RUNNING':
        return '실행 중', 'running'
    if run['status'] == 'ERROR' or run['errors']:
        return '오류', 'error'
    if run['failed']:
        return f'실패 {run["failed"]}건', 'fail'
    return ('정상', 'pass') if run['passed'] else ('결과 없음', 'idle')


def dashboard():
    all_projects = project_list()
    executions = run_list()
    head, button = st.columns([5, 1.3], vertical_alignment='center')
    with head:
        st.markdown('<div class="pilot-eyebrow">WORKSPACE TELEMETRY</div>', unsafe_allow_html=True)
        st.title('QA 워크스페이스')
        st.write('프로젝트를 생성하고 요구사항 기반 테스트를 실행하세요.')
    with button:
        if st.button('＋ 새 프로젝트', type='primary', width='stretch', key='home_new'):
            new_project_dialog()
    today = datetime.now(timezone(timedelta(hours=9))).date()
    totals = run_totals(executions)
    daily = run_totals([r for r in executions if run_date(r['started_at']) == today])
    tested = sum(bool(p['last_run']) for p in all_projects)
    metric_tiles(
        [
            (
                '활성 프로젝트 수',
                len(all_projects),
                'folder_copy',
                f'{tested}개 프로젝트 실행 이력',
                100 * tested / max(1, len(all_projects)),
                '#0051d5',
                '',
            ),
            (
                '오늘 실행된 테스트',
                daily['total'],
                'bolt',
                f'통과 {daily["passed"]}건 · 한국 시간 기준',
                daily['pct'],
                '#009668',
                '',
            ),
            (
                '전체 성공률',
                totals['rate'],
                'verified',
                f'통과 {totals["passed"]} / 전체 {totals["total"]}',
                totals['pct'],
                '#009668',
                '',
            ),
        ]
    )
    section_header('최근 프로젝트', '최대 4개 표시', '전체 프로젝트 더보기 →', 'more_projects', '프로젝트')
    visible = all_projects[:4]
    if not visible:
        st.info('표시할 프로젝트가 없습니다. 새 프로젝트를 만들어 시작하세요.')
    latest = {}
    for run in executions:
        latest.setdefault(run['project_id'], run)
    for col, project in zip(st.columns(4), visible):
        with col, st.container(border=True, key=f'project_card_{project["id"]}'):
            last = latest.get(project['id'])
            label, cls = card_state(last)
            stamp = local_time(last['started_at']) if last else ''
            result = run_totals([last] if last else [])
            failing = bool(last and (last['failed'] or last['errors']))
            st.markdown(
                f'<div class="pilot-card-top"><span class="pilot-state state-{cls}">● {label}</span><time>{stamp}</time></div>'
                f'<div class="project-heading"><strong>{html.escape(project["name"])}</strong></div>'
                f'<div class="project-url">{ICONS["link"]}{html.escape(project["target_url"])}</div>'
                + tag_chips(json.loads(project['tags']))
                + f'<div class="pilot-pass {"fail" if failing else ""}"><span>통과율 <b>{result["rate"]}</b></span>'
                f'<span>{result["passed"]} / {result["total"]} 통과</span></div>'
                f'<div class="pilot-track"><i style="width:{result["pct"]}%;background:{"#ba1a1a" if failing else "#009668"}"></i></div>',
                unsafe_allow_html=True,
            )
            actions = st.columns(2)
            actions[0].button(
                '상세 보기', key=f'open_{project["id"]}', width='stretch', on_click=open_project, args=(project['id'],)
            )
            actions[1].button(
                '▷ 바로 실행',
                key=f'launch_{project["id"]}',
                type='primary',
                width='stretch',
                on_click=quick_run,
                args=(project['id'],),
                disabled=not project['case_count'],
            )
    st.write('')
    section_header('최근 실행 기록', '최대 5개 표시', '전체 실행 기록 더보기 →', 'more_runs', '실행 기록')
    render_runs(executions[:5])


def project_collection():
    all_projects = project_list()
    executions = run_list()
    latest = {}
    for run in executions:
        latest.setdefault(run['project_id'], run)
    head, stat, button = st.columns([4.2, 1.5, 1.3], vertical_alignment='center')
    with head:
        st.markdown(
            '<div class="pilot-eyebrow">QA AUTOMATION WORKSPACE <i>•</i> <b>단일 페이지 검증</b></div>',
            unsafe_allow_html=True,
        )
        st.title('프로젝트 목록')
        st.write('각 프로젝트는 웹페이지 하나의 요구사항·테스트·실행 기록을 독립적으로 관리합니다.')
    stat.markdown(
        f'<div class="pilot-stat"><div><small>검사 중인 대상 URL</small><b>{len({p["target_url"] for p in all_projects})}개 웹페이지</b></div>'
        f'<span>{ICONS["link"]}</span></div>',
        unsafe_allow_html=True,
    )
    with button:
        if st.button('＋ 새 프로젝트 생성', type='primary', width='stretch', key='collection_new'):
            new_project_dialog()
    tag_counts = Counter(t for p in all_projects for t in json.loads(p['tags']))
    with st.container(border=True, key='project_toolbar'):
        search_col, sort_col = st.columns([3, 1.1], vertical_alignment='center')
        search = search_col.text_input(
            '프로젝트 검색',
            placeholder='프로젝트명 또는 대상 URL 검색 (예: example.com)',
            key='project_search',
            label_visibility='collapsed',
        )
        sort = sort_col.selectbox(
            '정렬', PROJECT_SORTS, key='project_sort', label_visibility='collapsed', format_func=lambda s: '정렬: ' + s
        )
        tags = (
            st.pills(
                '태그 필터',
                sorted(tag_counts),
                selection_mode='multi',
                format_func=lambda t: f'#{t}  {tag_counts[t]}',
                key='project_tags',
                help='선택한 태그 중 하나라도 포함한 프로젝트를 표시합니다.',
            )
            or []
        )
    visible = project_list(search, tags)

    def pass_rate(project):
        totals = run_totals([latest[project['id']]]) if project['id'] in latest else {'total': 0}
        return totals['pct'] if totals['total'] else 101  # never-run projects last

    if sort == '이름순':
        visible.sort(key=lambda p: p['name'].casefold())
    elif sort == '통과율 낮은순':
        visible.sort(key=pass_rate)
    page_items, footer = pager(visible, 'projects', (search, tuple(tags), sort), PROJECT_PAGE_SIZE, '프로젝트')
    if not visible:
        st.info('조건에 맞는 프로젝트가 없습니다.')
    for offset in range(0, len(page_items), 3):
        for col, project in zip(st.columns(3), page_items[offset : offset + 3]):
            with col, st.container(border=True, key=f'project_tile_{project["id"]}'):
                project_card(project, latest.get(project['id']))
    footer()


def project_card(project, last):
    pid = project['id']
    label, cls = card_state(last)
    label = '정상 운영' if cls == 'pass' else label
    totals = run_totals([last]) if last else {'total': 0, 'pct': 0, 'passed': 0}
    problems = (last['failed'] + last['errors']) if last else 0
    rate = (
        f'{totals["pct"]:g}% PASS' + (f' ({problems} 실패)' if problems else '')
        if totals['total']
        else '실행 기록 없음'
    )
    overview = (project['overview'] or '').strip().split('\n')[0] or '전체 요구사항을 아직 작성하지 않았습니다.'
    link = safe_link(project['target_url'])
    st.markdown(
        f'<div class="pc-head"><span class="pc-icon">{ICONS["window"]}</span><div class="pc-title">'
        f'<strong>{html.escape(project["name"])}</strong><p>{html.escape(overview)}</p></div>'
        f'<span class="pilot-state state-{cls}">● {label}</span></div>'
        f'<div class="pc-url"><span>{ICONS["link"]}</span><code>{html.escape(project["target_url"])}</code>'
        + (
            f'<a href="{link}" target="_blank" rel="noopener noreferrer" title="웹페이지 열기">{ICONS["external"]}</a>'
            if link
            else ''
        )
        + '</div>'
        + tag_chips(json.loads(project['tags']))
        + f'<div class="pc-metrics"><header><span>QA 메트릭 상태</span><b class="tone-{cls}">{rate}</b></header>'
        f'<div class="pilot-track"><i style="width:{totals["pct"]}%;background:{"#ba1a1a" if problems else "#009668"}"></i></div>'
        f'<dl><div><dt>요구사항</dt><dd>{project["req_count"]}개</dd></div>'
        f'<div><dt>등록 테스트</dt><dd>{project["case_count"]}개</dd></div>'
        f'<div><dt>최근 소요</dt><dd>{format_duration(run_seconds(last))}</dd></div></dl></div>',
        unsafe_allow_html=True,
    )
    run_col, manage_col = st.columns(2)
    run_col.button(
        '▷ 즉시 실행',
        key=f'launch_{pid}',
        width='stretch',
        on_click=quick_run,
        args=(pid,),
        disabled=not project['case_count'],
    )
    manage_col.button('프로젝트 관리 →', key=f'open_{pid}', width='stretch', on_click=open_project, args=(pid,))


def set_page(key, page):
    st.session_state[key + '_page'] = page


def page_numbers(page, pages):
    first = max(1, min(page - 2, pages - 4))
    return range(first, min(pages, first + 4) + 1)


def pager(items, key, filters, size, unit, size_options=None):
    """Slice items for the current page; the returned footer draws the summary and page buttons."""
    if st.session_state.get(key + '_filters') != repr(filters):
        st.session_state[key + '_filters'] = repr(filters)
        st.session_state[key + '_page'] = 1
    pages = max(1, -(-len(items) // size))
    page = min(int(st.session_state.get(key + '_page', 1)), pages)
    st.session_state[key + '_page'] = page
    start = (page - 1) * size

    def footer():
        if not items:
            return
        with st.container(key=f'{key}_pager', horizontal=True, vertical_alignment='center'):
            st.markdown(
                f'<div class="pilot-pager-text">전체 <b>{len(items)}</b>개 {unit} 중 '
                f'<b>{start + 1} - {min(start + size, len(items))}</b> 표시</div>',
                unsafe_allow_html=True,
            )
            if size_options:
                st.selectbox(
                    '페이지당 표시',
                    size_options,
                    key=key + '_size',
                    format_func=lambda n: f'{n}개씩 보기',
                    label_visibility='collapsed',
                )
            if pages > 1:
                st.button('‹', key=f'{key}_prev', disabled=page == 1, on_click=set_page, args=(key, page - 1))
                for number in page_numbers(page, pages):
                    st.button(
                        str(number),
                        key=f'{key}_p{number}',
                        type='primary' if number == page else 'tertiary',
                        on_click=set_page,
                        args=(key, number),
                    )
                st.button('›', key=f'{key}_next', disabled=page == pages, on_click=set_page, args=(key, page + 1))

    return items[start : start + size], footer


def reset_history_filters():
    for key in ('history_search', 'history_tags', 'history_period', 'history_status'):
        st.session_state.pop(key, None)


def runs_csv(runs):
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ['실행 ID', '프로젝트', '대상 URL', '상태', 'PASS', 'FAIL', 'ERROR', '소요 시간(초)', '시작(한국 시간)']
    )
    for run in runs:
        seconds = run_seconds(run)
        started = datetime.fromisoformat(run['started_at'])
        started = (started if started.tzinfo else started.replace(tzinfo=timezone.utc)).astimezone(
            timezone(timedelta(hours=9))
        )
        writer.writerow(
            [
                run['run_id'],
                run['name'],
                run['target_url'],
                run_state(run),
                run['passed'],
                run['failed'],
                run['errors'],
                '' if seconds is None else round(seconds, 1),
                started.strftime('%Y-%m-%d %H:%M:%S'),
            ]
        )
    return '﻿' + buffer.getvalue()  # BOM so Excel opens Korean text correctly


def workspace_history():
    with st.container(border=True, key='history_header'):
        head, actions = st.columns([3, 1.5], vertical_alignment='bottom')
        head.markdown(
            '<div class="pilot-crumb">워크스페이스 <i>›</i> <b>실행 파이프라인 기록</b></div>', unsafe_allow_html=True
        )
        head.title('전체 실행 기록')
        head.write('모든 프로젝트의 자동화 QA 테스트 실행 내역과 상세 리포트입니다. 날짜는 한국 시간 기준입니다.')
    metrics_area = st.container()
    with st.container(border=True, key='history_filters'):
        search_col, tag_col, date_col = st.columns([2.2, 1.6, 1.6], vertical_alignment='center')
        search = search_col.text_input(
            '프로젝트 또는 실행 ID',
            placeholder='프로젝트 또는 실행 ID 검색',
            key='history_search',
            label_visibility='collapsed',
        )
        tags = tag_col.multiselect(
            '태그',
            all_tags(),
            key='history_tags',
            placeholder='모든 태그',
            label_visibility='collapsed',
            help='선택한 태그 중 하나라도 포함한 프로젝트의 기록을 표시합니다.',
        )
        period = date_col.date_input(
            '기간',
            value=[],
            key='history_period',
            format='YYYY.MM.DD',
            label_visibility='collapsed',
            help='시작일과 종료일을 고르세요. 비워 두면 전체 기간입니다.',
        )
        state_col, reset_col = st.columns([4, 1], vertical_alignment='center')
        status = (
            state_col.segmented_control(
                '실행 상태', RUN_STATES, default='전체', key='history_status', label_visibility='collapsed'
            )
            or '전체'
        )
        reset_col.button('↺ 필터 초기화', key='history_reset', on_click=reset_history_filters, width='stretch')
    start = period[0] if len(period) >= 1 else None
    end = period[1] if len(period) == 2 else start
    runs = [
        r
        for r in run_list(tags, start, end)
        if search.casefold() in (r['name'] + ' ' + r['run_id']).casefold()
        and (status == '전체' or status == run_state(r))
    ]
    durations = [s for s in (run_seconds(r) for r in runs) if s is not None]
    totals = run_totals(runs)
    failed, errors = sum(r['failed'] for r in runs), sum(r['errors'] for r in runs)
    with metrics_area:
        metric_tiles(
            [
                (
                    '기간 내 총 실행',
                    f'{len(runs)}회',
                    'play',
                    f'{len({r["project_id"] for r in runs})}개 프로젝트',
                    None,
                    '',
                    '',
                ),
                (
                    '전체 통과율',
                    totals['rate'],
                    'verified',
                    f'통과 {totals["passed"]} / 전체 {totals["total"]}',
                    totals['pct'],
                    '#009668',
                    '',
                ),
                (
                    '평균 소요시간',
                    format_duration(sum(durations) / len(durations)) if durations else '—',
                    'timer',
                    '완료된 실행 기준',
                    None,
                    '',
                    '',
                ),
                (
                    '감지된 결함',
                    f'{failed}건',
                    'bug',
                    f'실행 오류 {errors}건은 별도 집계',
                    None,
                    '',
                    'alert' if failed else '',
                ),
            ],
            columns=4,
        )
    with actions, st.container(horizontal=True, horizontal_alignment='right', key='history_actions'):
        st.download_button(
            '⤓ CSV 리포트 내보내기',
            runs_csv(runs),
            file_name=f'testpilot-runs-{datetime.now(timezone(timedelta(hours=9))):%Y%m%d}.csv',
            mime='text/csv',
            key='history_csv',
            width='content',
            disabled=not runs,
        )
        st.button(
            '▷ 새 실행 시작',
            key='history_new_run',
            type='primary',
            width='content',
            on_click=open_workspace,
            args=('프로젝트',),
            help='프로젝트를 골라 바로 실행합니다.',
        )
    size = st.session_state.get('workspace_runs_size', 10)
    page_items, footer = pager(
        runs, 'workspace_runs', (tuple(tags), start, end, search, status, size), size, '결과', [10, 20, 50]
    )
    render_runs(page_items)
    footer()


def render_runs(recent):
    if not recent:
        st.info('표시할 실행 기록이 없습니다.')
        return
    with st.container(key='run_table'):
        widths = [1, 1.1, 2.6, 2, 1, 1.5, 1.2]
        for col, label in zip(
            st.columns(widths),
            ['상태', '실행 ID', '프로젝트 / 대상 URL', '실행 통계', '소요 시간', '실행 일시', '결과 리포트'],
        ):
            col.markdown('<div class="qa-table-label">' + label + '</div>', unsafe_allow_html=True)
        for run in recent:
            state = run_state(run)
            cls = state_class(state)
            with st.container(key=f'run_row_{cls}_{run["run_id"]}'):
                s, i, a, stat, d, b, c = st.columns(widths, vertical_alignment='center')
                s.markdown(f'<span class="pilot-state state-{cls}">● {state}</span>', unsafe_allow_html=True)
                i.markdown(f'<span class="qa-run-id">#{run["run_id"][:8]}</span>', unsafe_allow_html=True)
                a.markdown(
                    '<div class="qa-run-name">'
                    + html.escape(run['name'])
                    + '</div><div class="pilot-url">'
                    + html.escape(run['target_url'])
                    + '</div>'
                    + tag_chips(json.loads(run['tags'])),
                    unsafe_allow_html=True,
                )
                result = run_totals([run])
                problems = run['failed'] + run['errors']
                if run['status'] == 'RUNNING':
                    text = '진행 중'
                elif problems:
                    text = f'{run["passed"]} 통과 · {run["failed"]} 실패' + (
                        f' · {run["errors"]} 오류' if run['errors'] else ''
                    )
                else:
                    text = f'{run["passed"]} / {result["total"]} 통과 ({result["rate"]})'
                stat.markdown(
                    f'<div class="run-stat tone-{cls}">{text}</div><div class="pilot-track"><i style="width:{result["pct"]}%;'
                    f'background:{"#ba1a1a" if problems else "#009668"}"></i></div>',
                    unsafe_allow_html=True,
                )
                d.markdown(
                    f'<div class="qa-run-date">{format_duration(run_seconds(run))}</div>', unsafe_allow_html=True
                )
                b.markdown(
                    '<div class="qa-run-date">'
                    + str(run_date(run['started_at']).year)
                    + '년 '
                    + local_time(run['started_at'])
                    + '</div>',
                    unsafe_allow_html=True,
                )
                c.button(
                    '오류 확인' if problems else '결과 리포트',
                    key='recent_' + run['run_id'],
                    on_click=open_history,
                    args=(run['project_id'], run['run_id']),
                )


def project_header(project):
    pid = project['id']
    all_cases = cases(pid)
    runs = [r for r in run_list() if r['project_id'] == pid]
    name = html.escape(project['name'])
    link = safe_link(project['target_url'])
    head, actions = st.columns([3, 2.2], vertical_alignment='bottom')
    head.markdown(
        f'<div class="pilot-crumb">프로젝트 목록 <i>›</i> <b>{name}</b></div>'
        f'<div class="pilot-title"><h1>{name}</h1>{tag_chips(json.loads(project["tags"]))}</div>'
        + (
            f'<a class="pilot-link" href="{link}" target="_blank" rel="noopener noreferrer">{ICONS["external"]}{link}</a>'
            if link
            else f'<span class="pilot-link">{html.escape(project["target_url"])}</span>'
        ),
        unsafe_allow_html=True,
    )
    with actions, st.container(horizontal=True, horizontal_alignment='right', key='project_actions'):
        st.button('＋ 테스트 추가', key='header_add_test', on_click=open_add_test, args=(pid,))
        st.button(
            '▷ 전체 테스트 실행',
            key='header_run_all',
            type='primary',
            on_click=quick_run,
            args=(pid,),
            disabled=not any(c['reviewed'] for c in all_cases),
        )
        st.button(
            '최신 실행 리포트 보기',
            key='header_latest',
            on_click=open_history,
            args=(pid, runs[0]['run_id']) if runs else (pid, None),
            disabled=not runs,
        )
    view = st.session_state.project_view
    with st.container(key='project_nav', horizontal=True):
        for target, title in [
            ('요구사항', f'요구사항 & 테스트 관리 · {len(all_cases)}'),
            ('테스트', '테스트 추가'),
            ('실행', '테스트 실행'),
            ('실행 기록', f'실행 기록 · {len(runs)}건'),
            ('프로젝트 설정', '프로젝트 설정'),
        ]:
            st.button(
                title,
                key='project_tab_' + target,
                type='primary' if target == view else 'tertiary',
                on_click=open_project,
                args=(pid, target),
            )


def project_summary(project):
    pid = project['id']
    reqs, all_cases = requirements(pid), cases(pid)
    runs = [r for r in run_list() if r['project_id'] == pid]
    last = runs[0] if runs else None
    approved = sum(c['reviewed'] for c in all_cases)
    ai_made = sum(c.get('source') == 'ai' for c in all_cases)
    linked = len({c['requirement_id'] for c in all_cases})
    totals = run_totals(runs[:1])
    with st.container(border=True, key='project_summary'):
        st.subheader('QA 테스트 요약 및 지표')
        tiles = [
            ('총 요구사항', f'{len(reqs)}<small>건</small>', f'테스트 연결 {linked}건'),
            (
                '총 테스트 케이스',
                f'{len(all_cases)}<small>개</small>',
                f'AI {ai_made} · 기본 {len(all_cases) - ai_made}',
            ),
            (
                '실행 가능 비율',
                f'{100 * approved / len(all_cases):.0f}%' if all_cases else '—',
                f'승인 {approved} / 전체 {len(all_cases)}',
            ),
            (
                '최근 성공률',
                totals['rate'],
                f'PASS {last["passed"]} / FAIL {last["failed"]}' if last else '실행 기록 없음',
            ),
        ]
        st.markdown(
            '<div class="ps-grid">'
            + ''.join(
                f'<div><span>{label}</span><b>{value}</b><small>{detail}</small></div>'
                for label, value, detail in tiles
            )
            + '</div>',
            unsafe_allow_html=True,
        )
        if last:
            total = max(1, last['passed'] + last['failed'] + last['errors'])
            segments = [
                ('pass', last['passed'], '통과'),
                ('fail', last['failed'], '실패'),
                ('error', last['errors'], '오류'),
            ]
            st.markdown(
                f'<div class="ps-dist"><header><span>최근 실행 결과 분포</span><b>{last["passed"]} / {total} 통과</b></header>'
                '<div class="ps-bar">'
                + ''.join(f'<i class="{c}" style="width:{100 * n / total}%"></i>' for c, n, _ in segments if n)
                + '</div><div class="ps-legend">'
                + ''.join(f'<span class="{c}">● {label} {n}</span>' for c, n, label in segments if n)
                + '</div></div>'
                f'<div class="ps-run"><header><span>최근 실행</span><time>{local_time(last["started_at"])}</time></header>'
                f'<b>#{last["run_id"][:8]}</b><div><span class="pass">✓ {last["passed"]} 성공</span>'
                f'<span class="fail">✕ {last["failed"] + last["errors"]} 실패</span>'
                f'<span>⏱ {format_duration(run_seconds(last))}</span></div></div>',
                unsafe_allow_html=True,
            )
            st.button(
                '실행 결과·스크린샷 보기',
                key='summary_history',
                width='stretch',
                on_click=open_history,
                args=(pid, last['run_id']),
            )
        else:
            st.caption('아직 실행 기록이 없습니다. 상단의 전체 테스트 실행으로 시작하세요.')


def requirements_page(project):
    pid = project['id']
    with st.container(border=True, key='policy_card'):
        st.subheader('페이지 기본 규칙 및 예외 처리 정책')
        st.caption('모든 요구사항과 테스트에 공통으로 적용되는 기준입니다. AI 테스트 생성에도 함께 전달됩니다.')
        rule, exception = st.columns(2)
        for col, cls, label, value in [
            (rule, 'rule', '기본 요구사항 정책', project['overview']),
            (exception, 'exception', '예외사항 & 에러 핸들링', project['exceptions']),
        ]:
            col.markdown(
                f'<div class="pilot-policy {cls}"><b>● {label}</b><p>'
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
    reqs = requirements(pid)
    title, add = st.columns([4, 1.4], vertical_alignment='center')
    title.markdown(
        f'<div class="pilot-section"><strong>개별 요구사항별 테스트 그룹</strong><em>총 {len(reqs)}개 그룹</em></div>',
        unsafe_allow_html=True,
    )
    if add.button('＋ 새 요구사항 추가', key='new_requirement', type='primary', width='stretch'):
        new_requirement_dialog(pid)
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
    for number, req in enumerate(reqs, 1):
        group = grouped.get(req['id'], [])
        results = [outcomes.get(c['id']) for c in group]
        problems = sum(r in ('FAIL', 'ERROR') for r in results)
        if not group:
            verdict = ''
        elif problems:
            verdict = f'<span class="rg-badge fail">{problems}건 실패 발생</span>'
        elif all(r == 'PASS' for r in results):
            verdict = '<span class="rg-badge pass">전체 성공 (100%)</span>'
        else:
            verdict = '<span class="rg-badge idle">미실행 포함</span>'
        with st.container(border=True, key=f'req_group_{number}'):
            st.markdown(
                f'<div class="rg-head"><span class="rg-num">{number:02d}</span><div><div class="rg-title">{html.escape(req["title"] or req["id"])}'
                f'<span class="rg-badge">등록 테스트 {len(group)}개</span>{verdict}</div>'
                f'<div class="rg-desc">{html.escape(requirement_text(req).split(chr(10))[0])}</div></div></div>',
                unsafe_allow_html=True,
            )
            if group:
                rows = ''.join(
                    f'<tr class="{"fail" if outcomes.get(c["id"]) in ("FAIL", "ERROR") else ""}"><td><code>{html.escape(short_id(c["id"]))}</code></td>'
                    f'<td><b>{html.escape(c["description"])}</b><small>{html.escape(expected_text(c))}</small></td>'
                    f'<td>{"AI 생성" if c.get("source") == "ai" else ("결함 재현" if c.get("fault_variant") else "기본")}</td>'
                    f'<td>{"승인됨" if c["reviewed"] else "검토 필요"}</td>'
                    f'<td><span class="qa-status {str(outcomes.get(c["id"], "")).lower()}">{outcomes.get(c["id"], "미실행")}</span></td></tr>'
                    for c in group
                )
                st.markdown(
                    '<table class="rg-table"><thead><tr><th>ID</th><th>테스트 케이스 · 기대 동작</th><th>종류</th>'
                    f'<th>검토</th><th>최근 결과</th></tr></thead><tbody>{rows}</tbody></table>',
                    unsafe_allow_html=True,
                )
            left, right = st.columns([3, 1.4], vertical_alignment='center')
            left.button(
                '＋ 이 요구사항에 테스트 추가', key='add_to_' + req['id'], on_click=open_add_test, args=(pid, req['id'])
            )
            right.button(
                f'테스트 {len(group)}개 관리 →',
                key='to_tests_' + req['id'],
                width='stretch',
                on_click=open_project,
                args=(pid, '테스트', req['id']),
            )
            with st.expander('요구사항 내용 수정'):
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


def open_history(project_id, run_id):
    open_project(project_id, '실행 기록')
    st.session_state[f'selected_run_{project_id}'] = run_id


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
            kind = st.radio(
                '기본 테스트',
                list(templates),
                format_func=lambda k: templates[k]['description'],
                captions=[templates[k]['summary'] for k in templates],
                key=f'template_kind_{pid}_{rid}',
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
        toggle_col, generate_col = st.columns([1.5, 1], vertical_alignment='center')
        use_page = toggle_col.toggle(
            '페이지 구조 자동 읽기',
            value=True,
            key=f'use_page_{pid}_{rid}',
            help='등록한 URL과, 그 페이지의 링크·요구사항에 적힌 같은 사이트 경로(예: /home)를 브라우저로 조회해 '
            '입력창·버튼·링크·안내 영역의 선택자를 AI에 전달합니다. 입력·제출은 하지 않고 입력값도 읽지 않으며, '
            '로그아웃·삭제처럼 상태를 바꿀 수 있는 링크는 열지 않습니다.',
        )
        draft_key = f'drafts_{pid}_{rid}'
        generate = generate_col.button(
            '✦ AI 테스트 생성',
            type='primary',
            disabled=not prompt.strip(),
            width='stretch',
            key=f'generate_{pid}_{rid}',
        )
        st.caption('전체 기준과 선택한 요구사항을 함께 전달합니다. 생성 후 검토하세요.')
        if generate:
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
        drafts = st.session_state.get(draft_key, [])
        revision = st.session_state.get(draft_key + '_revision', 0)
        chosen = []
        if drafts:
            st.markdown('<div class="ai-preview-label">AI 생성 프리뷰 결과</div>', unsafe_allow_html=True)
        for index, draft in enumerate(drafts):
            saved = bool(draft.get('_saved_case_id'))
            with st.container(border=True, key=f'ai_draft_{index}'):
                st.markdown(
                    f'<div class="ai-draft-head"><code>AI-{index + 1:02d}</code><strong>{html.escape(draft["description"])}</strong>'
                    f'<span class="{"saved" if saved else "ready"}">● {"등록 완료" if saved else "생성 완료 · 검토 필요"}</span></div>'
                    f'<div class="ai-draft-expected">{html.escape(draft["expected"])}</div>'
                    '<div class="ai-steps"><b>실행 절차 단계 (Generated Steps)</b><ol>'
                    + ''.join(
                        f'<li>{ACTION_LABELS.get(s["action"], s["action"])}'
                        + (f' <code>{html.escape(s.get("selector", ""))}</code>' if s.get('selector') else '')
                        + (f' <span>{html.escape(s.get("value", ""))}</span>' if s.get('value') else '')
                        + '</li>'
                        for s in draft['steps']
                    )
                    + '</ol></div>',
                    unsafe_allow_html=True,
                )
                if draft.get('review_notes'):
                    st.warning(draft['review_notes'])
                with st.expander('단계와 선택자 수정'):
                    steps = step_editor(draft['steps'], f'ai_steps_{pid}_{rid}_{revision}_{index}')
                selector_check_view(
                    project, draft, steps, f'{pid}_{rid}_{revision}_{index}', (context_info or {}).get('paths', ())
                )
                approved = st.checkbox(
                    '목록 추가 대상 포함 · 실행 단계와 선택자를 확인했습니다',
                    key=f'ai_approved_{pid}_{rid}_{revision}_{index}',
                    disabled=saved,
                )
                if approved and not saved:
                    chosen.append((draft, steps))
        if drafts:
            with st.container(key='adder_footer', horizontal=True, vertical_alignment='center'):
                st.markdown(
                    f'<div class="adder-count">선택된 AI 테스트 <b>{len(chosen)}</b>개'
                    '<small>추가하면 이 요구사항의 테스트 목록에 승인된 상태로 등록됩니다.</small></div>',
                    unsafe_allow_html=True,
                )
                if st.button('취소', key=f'adder_cancel_{pid}_{rid}'):
                    close_case_adder()
                    st.rerun()
                if st.button(
                    '＋ 테스트 목록에 추가하기', key=f'adder_save_{pid}_{rid}', type='primary', disabled=not chosen
                ):
                    added, problems = 0, []
                    for draft, steps in chosen:
                        try:
                            draft['_saved_case_id'] = save_case(pid, rid, dict(draft, steps=steps), reviewed=True)
                            added += 1
                        except ValueError as error:
                            problems.append(f'{draft["description"]}: {error}')
                    if problems:
                        st.error(' / '.join(problems))
                    else:
                        st.session_state[f'tests_added_{pid}'] = (
                            f'AI 테스트 {added}개를 추가했습니다. 등록된 테스트에서 확인하세요.'
                        )
                        close_case_adder()
                        st.rerun()


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
        notice = st.session_state.pop(f'run_notice_{pid}', None)
        if notice:
            st.warning(notice)
        running = background.active_job(pid)
        if st.button('▶ 테스트 실행', type='primary', width='stretch', disabled=not selected or bool(running)):
            try:
                st.session_state[f'run_job_{pid}'] = background.start(pid, selected, variant, analyze=auto_analyze)
            except ValueError as error:
                st.error(str(error))
        run_progress(pid)
        if st.session_state.get(f'last_project_run_{pid}'):
            st.button('실행 기록 보기 →', on_click=open_project, args=(pid, '실행 기록'), width='stretch')


@st.fragment(run_every=1)
def run_progress(pid):
    """Redraws only this panel every second while a background run is going."""
    job = background.get(st.session_state.get(f'run_job_{pid}'))
    if not job:
        return
    if job['phase'] in background.ACTIVE:
        label = {
            'starting': '브라우저를 준비하고 있습니다…',
            'running': f'{job["done"]} / {job["total"]}개 완료',
            'analyzing': '실패 항목을 AI로 분석하고 있습니다…',
        }[job['phase']]
        st.progress(job['done'] / job['total'] if job['total'] else 0.0, text=label)
        st.caption('다른 화면으로 이동해도 실행은 계속됩니다.')
        return
    if st.session_state.get(f'run_job_seen_{pid}') == job['id']:
        if job['phase'] == 'failed':
            st.error(job['error'])
        else:
            st.success('실행 완료')
            if job['warnings']:
                st.warning('일부 실패는 AI 분석을 하지 못했습니다: ' + ', '.join(job['warnings']))
        return
    # First redraw after the run ended: remember the run and refresh the whole page once.
    st.session_state[f'run_job_seen_{pid}'] = job['id']
    if job['run_id']:
        st.session_state[f'selected_run_{pid}'] = job['run_id']
        st.session_state[f'last_project_run_{pid}'] = job['run_id']
    st.rerun()


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
