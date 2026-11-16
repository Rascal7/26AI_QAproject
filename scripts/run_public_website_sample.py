"""Register and genuinely execute read-only checks against a public website."""

from qa_system import storage
from qa_system.projects import create_project, save_requirement, save_case, cases
from qa_system.runner import run_suite


def main():
    name = '실제 웹사이트 QA · Example Domain'
    existing = storage.rows('SELECT id FROM projects WHERE name=? AND target_url=?', (name, 'https://example.com/'))
    if existing:
        project_id = existing[0]['id']
    else:
        project_id = create_project(
            name,
            'https://example.com/',
            '공개 운영 페이지를 실제 Chromium 브라우저로 검사합니다. HTTP 200, 제목, 안내 링크의 표시를 확인합니다.',
            '로그인·폼 제출·DB 검증은 범위 밖입니다. 외부 안내 링크는 클릭하지 않습니다. 네트워크 장애는 실행 오류로 기록됩니다.',
            tags=['실제 웹사이트', '공개 페이지', '기본 점검'],
        )
        checks = [
            ('페이지 접속', 'HTTPS 페이지가 HTTP 200으로 응답한다.', {'action': 'assert_status', 'value': '200'}),
            (
                '제목 표시',
                '주 제목에 Example Domain이 표시된다.',
                {'action': 'assert_text', 'selector': 'h1', 'value': 'Example Domain'},
            ),
            (
                '안내 링크 표시',
                'IANA 안내 링크가 화면에 표시된다.',
                {'action': 'assert_visible', 'selector': 'a[href*="iana.org"]', 'value': ''},
            ),
        ]
        for title, expected, assertion in checks:
            requirement = save_requirement(project_id, title, expected)
            save_case(
                project_id,
                requirement,
                dict(
                    engine='web',
                    description=title,
                    expected=expected,
                    steps=[{'action': 'navigate', 'value': ''}, assertion],
                ),
                reviewed=True,
            )
    run_id = run_suite([case['id'] for case in cases(project_id)], project_id=project_id)
    print(
        storage.encode(
            {
                'project_id': project_id,
                'run_id': run_id,
                'results': storage.rows('SELECT case_id,outcome FROM test_results WHERE run_id=?', (run_id,)),
            }
        )
    )


if __name__ == '__main__':
    main()
