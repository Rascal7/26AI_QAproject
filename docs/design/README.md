# QA Lab · 프로젝트 워크스페이스

## 현재 적용 디자인 · TestPilot (2026-11-06)

사용자가 제공한 `stitch_web_qa_management_ui.zip`의 HTML, 화면 이미지 및 디자인 명세는 `user-stitch/stitch_web_qa_management_ui/`에 있습니다. Figma의 편집 가능한 화면은 [대시보드](https://www.figma.com/design/XQCufmFAXFWQjHWfsjOf3S?node-id=12-29), [프로젝트 목록](https://www.figma.com/design/XQCufmFAXFWQjHWfsjOf3S?node-id=11-29), [요구사항 관리](https://www.figma.com/design/XQCufmFAXFWQjHWfsjOf3S?node-id=10-29), [테스트 추가](https://www.figma.com/design/XQCufmFAXFWQjHWfsjOf3S?node-id=8-29), [실행 기록](https://www.figma.com/design/XQCufmFAXFWQjHWfsjOf3S?node-id=9-29)입니다.

대시보드와 프로젝트 목록의 아이콘은 벡터로 교체했습니다. 다른 세 화면은 Figma MCP 플랜 한도로 일부 아이콘이 영문 이름으로 남았습니다. Figma 데스크톱에서 `Plugins → Development → Import plugin from manifest`를 열고 `testpilot-finish/manifest.json`을 선택한 뒤, 해당 디자인 파일에서 플러그인을 실행하면 남은 아이콘이 교체됩니다. 플러그인은 지정된 다섯 프레임에만 적용됩니다.

웹은 실제 프로젝트와 실행 데이터로 지표를 계산하며, 현재 지원하는 동작만 탐색 메뉴에 표시합니다. 데스크톱과 모바일 검증 캡처는 `artifacts/testpilot-preview/`에 있습니다.

## 이전 Google Stitch 디자인 (2026-11-05)

- 프로젝트: `4113184446537489753` — QA Lab — Korean QA Workspace (PRIVATE)
- 홈 화면: `f3bcd82879bf43b2881e3ca2ad6915b7`
- MCP 연결: `https://stitch.googleapis.com/mcp`. Codex 사용자 설정에 등록했고, 현재 작업은 `scripts/stitch_mcp.py`로 같은 MCP 엔드포인트를 호출했습니다.
- 생성 요청: `stitch-home-request.json`. 원본 화면: `stitch-home.html`, `stitch-home.png`. 디자인 시스템: `STITCH_DESIGN.md`.
- 앱 적용: `qa_system/stitch.css`, `qa_system/project_ui.py`, `streamlit_app.py`, `.streamlit/config.toml`.
- 흰색 사이드바, #F8FAFC 배경, #2563EB 주요 동작, #0F172A 본문, #E2E8F0 테두리. 상태 배지와 태그를 분리하고 프로젝트 카드를 2열로 배치합니다.
- Stitch의 예시 수치, 임의 버전 및 브라우저 버전은 채택하지 않았습니다. 실제 SQLite 데이터와 Streamlit 버튼을 연결해 기존 실행·저장·상세 기록 기능을 유지합니다.
- 키는 Git 제외 `.env`와 사용자 MCP 설정에만 저장하며 디자인 산출물에는 포함하지 않습니다. MCP 생성 요청은 재실행 시 추가 화면을 만들므로 무조건 재실행하지 마세요.

## 이전 Figma 디자인 기록

[Figma 디자인 파일](https://www.figma.com/design/XQCufmFAXFWQjHWfsjOf3S?node-id=5-625)

| 화면 | Figma 노드 |
|---|---|
| 프로젝트 대시보드 | 5:625 |
| 프로젝트 요구사항 | 5:740 |
| 요구사항별 AI 테스트 | 5:778 |

Figma의 Simple Design System 버튼·카드 인스턴스와 편집 가능한 한글 텍스트, Auto Layout으로 구성했습니다. 전체 화면을 평면 이미지로 붙이지 않았습니다.
사용 폰트는 Noto Sans KR이며 웹에서는 Noto Sans KR / Malgun Gothic / sans-serif 순으로 표시합니다.
디자인의 쇼핑몰 프로젝트는 배치 확인을 위한 예시입니다. 실제 앱은 SQLite에 저장된 프로젝트만 표시합니다.

색상: 배경 #F7F8FC, 사이드바 #171D30, 주요 동작 #6C5CE7, 본문 #22283E.
메인 동작은 새 프로젝트 / 프로젝트 열기로 줄이고, 프로젝트 안에 요구사항 / 테스트 / 실행 / 실행 기록을 배치했습니다.
실행 기록의 결과·실패 분석·보고서 탭은 유지합니다.

`create-figma.js`는 디자인 작성 기록입니다. 다시 실행하면 프레임이 추가되므로 기존 파일에 무조건 재실행하지 않습니다.
