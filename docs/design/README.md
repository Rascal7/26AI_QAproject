# QA Lab · 프로젝트 워크스페이스

## 현재 적용 디자인 · TestPilot (2026-11-06)

사용자가 제공한 `stitch_web_qa_management_ui.zip`의 HTML, 화면 이미지 및 디자인 명세는 `user-stitch/stitch_web_qa_management_ui/`에 있습니다. Figma의 편집 가능한 화면은 [대시보드](https://www.figma.com/design/XQCufmFAXFWQjHWfsjOf3S?node-id=12-29), [프로젝트 목록](https://www.figma.com/design/XQCufmFAXFWQjHWfsjOf3S?node-id=11-29), [요구사항 관리](https://www.figma.com/design/XQCufmFAXFWQjHWfsjOf3S?node-id=10-29), [테스트 추가](https://www.figma.com/design/XQCufmFAXFWQjHWfsjOf3S?node-id=8-29), [실행 기록](https://www.figma.com/design/XQCufmFAXFWQjHWfsjOf3S?node-id=9-29)입니다.

대시보드와 프로젝트 목록의 아이콘은 벡터로 교체했습니다. 다른 세 화면은 Figma MCP 플랜 한도로 일부 아이콘이 영문 이름으로 남았습니다. Figma 데스크톱에서 `Plugins → Development → Import plugin from manifest`를 열고 `testpilot-finish/manifest.json`을 선택한 뒤, 해당 디자인 파일에서 플러그인을 실행하면 남은 아이콘이 교체됩니다. 플러그인은 지정된 다섯 프레임에만 적용됩니다.

웹은 실제 프로젝트와 실행 데이터로 지표를 계산하며, 현재 지원하는 동작만 탐색 메뉴에 표시합니다. 데스크톱과 모바일 검증 캡처는 `artifacts/testpilot-preview/`에 있습니다.

### 2026-11-17 재정비

같은 zip(파일 내용 동일)의 다섯 화면에 더 가깝게 맞췄습니다. 실제 데이터와 기능으로 채울 수 있는 부분만 적용했습니다.

| 화면 | 반영 내용 |
|---|---|
| 대시보드 | 섹션 배지(최대 N개 표시), 카드의 **바로 실행**(승인된 테스트를 백그라운드 실행), 실행 표의 소요 시간·통계 막대·실패 행 강조·상태별 리포트 버튼 |
| 프로젝트 목록 | 아이콘·요약·상태 배지, URL 상자(새 창 열기), **QA 메트릭 상태** 박스(통과율·요구사항·등록 테스트·최근 소요), 즉시 실행 / 프로젝트 관리, 정렬(최근 실행·이름·통과율), 태그 칩(개수), 페이지당 6개 |
| 프로젝트 상세 | 경로 표시, 제목+태그, 테스트 추가 / 전체 테스트 실행 / 최신 리포트 버튼, 밑줄형 탭(개수), 기본·예외 정책 상자, 번호 붙은 요구사항 그룹과 결과 배지·테스트 표, 요약 패널(실행 가능 비율·결과 분포·최근 실행) |
| 실행 기록 | 아이콘 지표 4개(감지된 결함 강조), 상태 버튼 필터·기간·필터 초기화, **CSV 리포트 내보내기**, 페이지당 표시 개수와 페이지 이동 |
| AI 테스트 추가 | 페이지 구조 읽기 스위치와 생성 버튼, `AI-01` 미리보기 카드(번호 붙은 실행 단계), 여러 개를 골라 **한 번에 추가**하는 하단 막대 |

디자인에 있지만 기능이 없는 항목(스위트 트리 탐색기, 스케줄러·트리거, 알림, 사용자 아바타, 브라우저 종류, 예시 수치)은 넣지 않았습니다. 왼쪽 메뉴 아래의 "문서 & 사용 가이드"는 GitHub README로 연결합니다.

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
