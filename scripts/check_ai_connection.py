"""Small live API check. Never print credentials or provider request headers."""
from qa_system.ai import generate_project_cases
from qa_system.projects import get_project, requirements
from qa_system.storage import baseline_project_id
from qa_system.web_tests import validate_steps


def main():
    project_id=baseline_project_id()
    if project_id is None:
        raise SystemExit('기본 로그인 데모 프로젝트가 없습니다. python -m qa_system.runner --restore-demo 로 복구하세요.')
    project=get_project(project_id)
    try:
        drafts=generate_project_cases(project,requirements(project_id)[0],
            '테스트 1개만 만들어줘. 프로젝트 URL을 열고 h1에 QA 데모 로그인이라는 문구가 보이는지 확인해줘. 요소 선택자는 h1이야.')
        for draft in drafts:
            validate_steps(draft['steps'],project['target_url'])
        print('LIVE_AI_OK',len(drafts))
        print('actions:',[s['action'] for s in drafts[0]['steps']])
    except Exception as error:
        print('LIVE_AI_ERROR',type(error).__name__)
        print('status:',getattr(error,'status_code',None),'code:',getattr(error,'code',None))
        raise SystemExit(1)


if __name__=='__main__':
    main()
