import os
import json
import streamlit as st
from dotenv import load_dotenv
from demo_web.db import ROOT
from qa_system import storage
from qa_system.projects import get_project
from qa_system.project_ui import (
    dashboard,
    delete_project_dialog,
    execution_page,
    history_page,
    new_project_dialog,
    open_project,
    open_workspace,
    project_collection,
    project_header,
    project_summary,
    requirements_page,
    save_project,
    tests_page,
    workspace_history,
)

load_dotenv(ROOT / '.env')
storage.initialize()
storage.recover_stale_runs()
st.set_page_config(page_title='WebQA · QA 워크스페이스', page_icon='◈', layout='wide')
st.markdown(
    '<style>' + (ROOT / 'qa_system/stitch.css').read_text(encoding='utf-8') + '</style>', unsafe_allow_html=True
)
st.session_state.setdefault('project_id', None)
st.session_state.setdefault('project_view', '요구사항')
st.session_state.setdefault('workspace_view', '홈')
pid = st.session_state.project_id


def search_projects():
    st.session_state.project_search = st.session_state.top_search
    open_workspace('프로젝트')


with st.container(key='pilot_topbar', horizontal=True, vertical_alignment='center', gap='small'):
    st.markdown('<div class="pilot-brand"><b>✓</b> WebQA</div>', unsafe_allow_html=True)
    for target, label in [('홈', '대시보드'), ('프로젝트', '프로젝트 목록'), ('실행 기록', '실행 기록')]:
        st.button(
            label,
            key='top_' + target,
            type='primary' if pid is None and target == st.session_state.workspace_view else 'tertiary',
            on_click=open_workspace,
            args=(target,),
        )
    if st.button('＋ 새 프로젝트', key='top_new', type='primary'):
        new_project_dialog()
    st.text_input(
        '프로젝트 검색',
        placeholder='프로젝트 이름 또는 URL 검색',
        label_visibility='collapsed',
        key='top_search',
        on_change=search_projects,
    )
st.sidebar.caption('테스트 워크스페이스')
for label in ['홈', '프로젝트', '실행 기록']:
    st.sidebar.button(
        {'홈': '전체 현황', '프로젝트': '프로젝트 보관함', '실행 기록': '실행 파이프라인 기록'}[label],
        width='stretch',
        key='workspace_' + label,
        icon={'홈': ':material/home:', '프로젝트': ':material/folder_open:', '실행 기록': ':material/history:'}[label],
        type='primary' if pid is None and st.session_state.workspace_view == label else 'secondary',
        on_click=open_workspace,
        args=(label,),
    )
if pid is not None:
    try:
        project = get_project(pid)
    except ValueError:
        open_project()
        st.rerun()
    st.sidebar.divider()
    st.sidebar.caption(project['name'])
    for label in ['요구사항', '테스트', '실행', '실행 기록', '프로젝트 설정']:
        st.sidebar.button(
            label,
            width='stretch',
            key='nav_' + label,
            type='primary' if st.session_state.project_view == label else 'secondary',
            on_click=open_project,
            args=(pid, label),
        )
st.sidebar.divider()
st.sidebar.caption('AI 연결')
st.sidebar.write('● 키 설정됨' if os.getenv('OPENAI_API_KEY') else '○ 키 미설정')
st.sidebar.link_button(
    '문서 & 사용 가이드',
    'https://github.com/Rascal7/26AI_QAproject#readme',
    icon=':material/help:',
    width='stretch',
)
if pid is None:
    if st.session_state.workspace_view == '실행 기록':
        workspace_history()
    else:
        if st.session_state.workspace_view == '프로젝트':
            project_collection()
        else:
            dashboard()
else:
    project = get_project(pid)
    view = st.session_state.project_view
    project_header(project)
    if view == '요구사항':
        main, summary = st.columns([2.2, 1], gap='medium')
        with main:
            requirements_page(project)
        with summary:
            project_summary(project)
    elif view == '테스트':
        tests_page(project)
    elif view == '실행':
        execution_page(project)
    elif view == '실행 기록':
        history_page(project)
    else:
        with st.form('project_settings'):
            name = st.text_input('프로젝트 이름', project['name'])
            tags = st.text_input(
                '태그', ', '.join(json.loads(project['tags'])), help='쉼표로 구분하세요. 예: 로그인, DB, 회귀 테스트'
            )
            st.text_input('웹페이지 URL', project['target_url'], disabled=True)
            st.caption('실행 이력과 대상이 섞이지 않도록 다른 URL은 새 프로젝트로 등록하세요.')
            overview = st.text_area('전체 요구사항', project['overview'])
            exceptions = st.text_area('전체 예외사항', project['exceptions'])
            if st.form_submit_button('저장', type='primary'):
                try:
                    save_project(pid, name, overview, exceptions, tags=tags)
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
        st.divider()
        st.subheader('프로젝트 삭제')
        st.caption('프로젝트와 연결된 요구사항, 테스트, 실행 기록을 삭제합니다.')
        if st.button('프로젝트 삭제', key='delete_project'):
            st.session_state.delete_project_pending = pid
        if st.session_state.get('delete_project_pending') == pid:
            delete_project_dialog(project)
