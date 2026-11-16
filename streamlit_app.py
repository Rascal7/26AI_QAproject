import os
import json
from html import escape
import streamlit as st
from dotenv import load_dotenv
from demo_web.db import ROOT
from qa_system import storage
from qa_system.projects import get_project
from qa_system.project_ui import dashboard, open_project, requirements_page, tests_page, execution_page, history_page, save_project
from qa_system.project_ui import open_workspace, workspace_history, new_project_dialog, run_totals, open_history
from qa_system.projects import requirements, cases
from qa_system.workspace import run_list
from qa_system.project_ui import delete_project_dialog

load_dotenv(ROOT / '.env')
storage.initialize()
storage.recover_stale_runs()
st.set_page_config(page_title='TestPilot · QA 워크스페이스',page_icon='◈',layout='wide')
st.markdown('<style>' + (ROOT / 'qa_system/stitch.css').read_text(encoding='utf-8') + '</style>', unsafe_allow_html=True)
st.session_state.setdefault('project_id',None)
st.session_state.setdefault('project_view','요구사항')
st.session_state.setdefault('workspace_view','홈')
pid=st.session_state.project_id
def search_projects():
    st.session_state.project_search=st.session_state.top_search
    open_workspace('프로젝트')

with st.container(key='pilot_topbar', horizontal=True, vertical_alignment='center',gap='small'):
    st.markdown('<div class="pilot-brand"><b>✓</b> TestPilot</div>',unsafe_allow_html=True)
    for target,label in [('홈','대시보드'),('프로젝트','프로젝트 목록'),('실행 기록','실행 기록')]:
        st.button(label,key='top_'+target,type='primary' if pid is None and target==st.session_state.workspace_view else 'tertiary',on_click=open_workspace,args=(target,))
    if st.button('＋ 새 프로젝트',key='top_new',type='primary'):
        new_project_dialog()
    st.text_input('프로젝트 검색',placeholder='프로젝트 이름 또는 URL 검색',label_visibility='collapsed',key='top_search',on_change=search_projects)
st.sidebar.caption('테스트 워크스페이스')
for label in ['홈','프로젝트','실행 기록']:
    st.sidebar.button({'홈':'전체 현황','프로젝트':'프로젝트 보관함','실행 기록':'실행 파이프라인 기록'}[label],width='stretch',key='workspace_'+label,
        icon={'홈':':material/home:','프로젝트':':material/folder_open:','실행 기록':':material/history:'}[label],
        type='primary' if pid is None and st.session_state.workspace_view==label else 'secondary',
        on_click=open_workspace,args=(label,))
if pid is not None:
    try:
        project=get_project(pid)
    except ValueError:
        open_project(); st.rerun()
    st.sidebar.divider()
    st.sidebar.caption(project['name'])
    for label in ['요구사항','테스트','실행','실행 기록','프로젝트 설정']:
        st.sidebar.button(label,width='stretch',key='nav_'+label,
            type='primary' if st.session_state.project_view==label else 'secondary',on_click=open_project,args=(pid,label))
st.sidebar.divider()
st.sidebar.caption('AI 연결')
st.sidebar.write('● 키 설정됨' if os.getenv('OPENAI_API_KEY') else '○ 키 미설정')
st.sidebar.caption('프로젝트별 웹 QA')
if pid is None:
    if st.session_state.workspace_view=='실행 기록':
        workspace_history()
    else:
        dashboard(collection=st.session_state.workspace_view=='프로젝트')
else:
    project=get_project(pid)
    view=st.session_state.project_view
    st.caption('프로젝트 / '+project['name'])
    a,b=st.columns([5,1],vertical_alignment='center')
    a.title(project['name'])
    b.link_button('웹페이지 ↗',project['target_url'],width='stretch')
    st.markdown('<div class="project-url">'+escape(project['name'])+' · '+escape(project['target_url'])+'</div>',unsafe_allow_html=True)
    with st.container(key='project_nav',horizontal=True):
        for target,title in [('요구사항','요구사항 관리'),('테스트','테스트 추가'),('실행','테스트 실행'),('실행 기록','실행 기록'),('프로젝트 설정','설정')]:
            st.button(title,key='project_tab_'+target,type='primary' if target==view else 'tertiary',on_click=open_project,args=(pid,target))
    if view=='요구사항':
        main,summary=st.columns([2.2,1],gap='medium')
        with main:
            requirements_page(project)
        with summary,st.container(border=True):
            st.subheader('QA 테스트 요약 및 지표')
            executions=[r for r in run_list() if r['project_id']==pid]
            a,b=st.columns(2)
            a.metric('총 요구사항',len(requirements(pid)))
            b.metric('총 테스트 케이스',len(cases(pid)))
            st.metric('최근 성공률',run_totals(executions[:1])['rate'])
            if executions:
                st.button('최근 실행 리포트',on_click=open_history,args=(pid,executions[0]['run_id']))
    elif view=='테스트': tests_page(project)
    elif view=='실행': execution_page(project)
    elif view=='실행 기록': history_page(project)
    else:
        with st.form('project_settings'):
            name=st.text_input('프로젝트 이름',project['name'])
            tags=st.text_input('태그',', '.join(json.loads(project['tags'])),help='쉼표로 구분하세요. 예: 로그인, DB, 회귀 테스트')
            st.text_input('웹페이지 URL',project['target_url'],disabled=True)
            st.caption('실행 이력과 대상이 섞이지 않도록 다른 URL은 새 프로젝트로 등록하세요.')
            overview=st.text_area('전체 요구사항',project['overview'])
            exceptions=st.text_area('전체 예외사항',project['exceptions'])
            if st.form_submit_button('저장',type='primary'):
                try:
                    save_project(pid,name,overview,exceptions,tags=tags); st.rerun()
                except ValueError as error: st.error(str(error))
        st.divider()
        st.subheader('프로젝트 삭제')
        st.caption('프로젝트와 연결된 요구사항, 테스트, 실행 기록을 삭제합니다.')
        if st.button('프로젝트 삭제', key='delete_project'):
            st.session_state.delete_project_pending = pid
        if st.session_state.get('delete_project_pending') == pid:
            delete_project_dialog(project)
