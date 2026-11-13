# AI 웹 QA 자동화 프로젝트

프로젝트 기획·구조·UI/UX·AI 활용방안과 7주차 기획 / 9~11주차 구현·테스트 일정은 [프로젝트 개요](PROJECT_OVERVIEW.md)에 정리했습니다.

- GitHub (Public): https://github.com/Rascal7/26AI_QAproject
- Notion: https://www.notion.so/3eb65ab291e7815faa49c0bb80c996df

두 기획서에 맞춘 로컬 Flask 로그인 데모 + SQLite + pytest/Chromium + Streamlit QA 관리 도구입니다.

## 시작하기 (Windows)

처음 내려받았다면 아래 **설치 재현** 명령으로 가상환경·패키지·Chromium을 설치하세요. `data/qa.db`는 앱 시작 시 생성됩니다. 개인 DB와 과거 실행 증거는 저장소에 포함되지 않습니다.

1. `start_demo.cmd` 더블클릭 → http://127.0.0.1:5000/login
2. `start_qa.cmd` 더블클릭 → http://127.0.0.1:8501
3. 대시보드에서 **새 프로젝트** → 이름과 웹페이지 URL 등록
4. 프로젝트의 **요구사항**에서 전체 요구사항·예외사항을 저장하고 개별 요구사항 추가
5. **테스트**에서 요구사항 선택 → 기본 테스트 추가 또는 AI로 추가
6. **실행**에서 전체 또는 특정 요구사항의 테스트 실행 → **실행 기록** 확인

프로젝트 하나는 웹페이지 URL 하나를 관리합니다. 다른 URL은 새 프로젝트로 등록합니다.
기본 로그인 데모 프로젝트는 최초 실행 시 생성됩니다. 기존 설치의 프로젝트와 실행 기록은 로컬 DB에 보존됩니다.
새 프로젝트는 실제 등록 URL에 접속하며, 로그인 데모의 DB 기준 테스트만 별도 임시 서버·DB를 사용합니다.

기본 테스트는 페이지 접속, 요소 표시, 문구 확인, 클릭 후 이동, 입력 후 안내를 제공합니다.
요소 선택자(예: `#email`, `h1`)와 기대 문구는 대상 페이지에 맞게 수정한 뒤 추가하세요.
AI에는 원하는 테스트와 알고 있는 선택자를 입력합니다. 전체 기준과 선택한 요구사항도 함께 전달됩니다.
생성된 실행 단계를 검토·수정하고 **실행 단계와 선택자를 확인했습니다**를 체크한 뒤 프로젝트에 추가하세요.
기존 실행 기록의 결과·실패 분석·보고서 탭은 유지했고, 현재 프로젝트의 기록만 표시합니다.

디자인: [Figma — QA Lab 프로젝트 워크스페이스](https://www.figma.com/design/XQCufmFAXFWQjHWfsjOf3S?node-id=5-625)

가상환경 활성화나 Node.js/npm 설치는 필요하지 않습니다. 터미널을 닫으면 서버가 종료됩니다.
로그인 계정은 기획서의 로컬 데모 계정(`qa.user@example.com` / `QaDemo!234`)입니다.

## API 키 설정 — 사용자가 해야 하는 단계

`.env.example`을 `.env`로 복사하여 `OPENAI_API_KEY`를 본인의 OpenAI API 키로 채우고 QA 앱을 재시작하세요.
키는 채팅에 보내거나 Git에 올리지 마세요. API 계정의 결제/사용 한도 및 사용 가능한 모델은 본인 계정에서 설정해야 합니다.
`OPENAI_MODEL`은 수정 가능하며 기본값은 `gpt-4.1-mini`입니다. 계정에서 지원하는 Structured Outputs 모델을 사용하세요.
키가 없으면 실제 AI 호출만 비활성화되며 기준 테스트와 보고서는 사용할 수 있습니다.

AI 작업 순서: 프로젝트 → 테스트 → 요구사항 선택 → AI로 추가 → 요청 입력 → 테스트 생성 → 단계 검토·승인 → 추가 → 실행.
승인한 웹 테스트는 SQLite에 보존되며 앱을 다시 켜도 사용할 수 있습니다.
실제 비밀번호를 테스트 단계에 저장하지 마세요. `.env`의 `QA_TEST_PASSWORD`를 설정하고 입력값에는 `${QA_TEST_PASSWORD}`를 사용합니다.
OpenAI API 키는 테스트 실행 프로세스에 전달하지 않습니다.

## 설치 재현

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

SQLite는 Python 기본 라이브러리입니다. 별도 DB 서버를 설치할 필요가 없습니다.

## 검증

```powershell
# 기준 10개 + 실행 결과 DB/증거/보고서 저장
.\.venv\Scripts\python.exe -m qa_system.runner
# 순서 반전 독립성 검증
.\.venv\Scripts\python.exe -m qa_system.runner --reverse
# 결함 실험: 각 실행에서 해당 DB 기준 1개가 FAIL이어야 정상적인 탐지
.\.venv\Scripts\python.exe -m qa_system.runner --variant skip_disabled
.\.venv\Scripts\python.exe -m qa_system.runner --variant skip_lock
.\.venv\Scripts\python.exe -m qa_system.runner --variant skip_revalidation
# pytest 직접 실행 (QA DB 저장은 runner 이용)
.\.venv\Scripts\python.exe -m pytest
```

수동 데모는 5000 포트를 유지하고, 데모의 DB 기준 테스트는 OS가 할당하는 루프백 포트를 씁니다. 수동 서버와의 충돌 없이 테스트별 DB를 연결하기 위한 구현상 조정입니다.
데모의 DB 기준 테스트는 테스트별 새 SQLite DB와 브라우저 컨텍스트를 사용하고 종료 시 서버·연결·임시 DB를 정리합니다. 일반 웹 테스트는 등록 URL에 새 브라우저 컨텍스트로 접속합니다. `data/demo.db`와 `data/qa.db`는 자동 삭제하지 않습니다.

## 저장 위치와 판정

- `data/demo.db`: 수동 데모 사용자. 기존 데이터 보존.
- `data/qa.db`: 프로젝트, 요구사항, 시나리오, 검토한 케이스, 실행 이력, 결과, 버그 및 보고서.
- `artifacts/<실행ID>/`: 보고서, pytest 로그, 스크린샷, 민감정보를 제거한 Playwright trace, 실행 코드.
- PASS: HTTP/화면/세션/DB가 기대와 일치. 예상한 401·403·503도 PASS.
- FAIL: 준비 완료 후 assertion 불일치. 버그 근거로 기록.
- ERROR: 준비/실행 환경/코드 오류. 제품 결함 및 커버리지에서 제외.

스크린샷은 비밀번호 입력을 마스킹합니다. trace는 DOM 스냅샷·소스·네트워크 본문을 보존하지 않으며 호출 정보의 비밀번호·쿠키도 제거합니다. HTTP 상태/오류 코드 증거는 별도 결과 JSON과 DB에 남습니다.
성공 후 즉시 이동하는 페이지에서 Chromium이 응답 본문을 해제할 수 있으므로, HTTP 상태는 브라우저에서, 실제 응답 JSON은 테스트 전용 서버 관찰자로 수집합니다. 응답 모킹이나 공개 검사 API는 사용하지 않습니다.

## AI 실행 범위

새 웹 프로젝트의 AI 테스트는 등록된 브라우저 동작(이동·입력·클릭·키 입력·HTTP/문구/요소/URL 확인)을 조합합니다.
임의 Python·JavaScript·SQL을 생성해서 실행하지 않습니다. 프로젝트와 같은 사이트의 경로만 탐색하며, 실행에는 시간 제한을 적용합니다.
페이지 DOM을 자동으로 읽어 AI에 전달하는 기능은 없습니다. 사용자가 선택자를 제공하지 않으면 AI가 추정하므로 검토가 필요합니다.
각 테스트에는 결과 확인 단계가 적어도 하나 있어야 합니다. DB 상태 변경 fixture는 기존 로그인 데모에서만 지원합니다.
기존 데모의 기준 10개와 결함 실험은 그대로 사용할 수 있습니다. 이전 형식 AI 테스트는 표시된 고정 실행 코드를 승인한 뒤 실행합니다.

전체 테스트: `.\.venv\Scripts\python.exe -m pytest`
프로젝트 UI 검증은 `scripts/check_project_ui.py`에서 별도 8503 서버와 테스트용 QA DB를 사용합니다. `QA_DB_PATH` 환경변수로 검증 DB를 분리할 수 있습니다.

API 구현 참고: [OpenAI Structured Outputs 공식 문서](https://developers.openai.com/api/docs/guides/structured-outputs).

GitHub 저장소에는 앱 소스·테스트·설치 안내를 제공합니다. 로컬 실행에 GitHub 계정은 필요하지 않습니다.

## 실제 웹사이트 검사와 프로젝트 삭제

`실제 웹사이트 QA · Example Domain` 프로젝트에는 공개 URL에 Chromium으로 접속한 실행 결과가 저장되어 있습니다. 실행 `87da0bfc43564f2e`는 HTTP 200 및 안내 링크 표시 PASS 2건, 예상한 h1 제목 부재 FAIL 1건입니다. 제목 실패는 기대 구조와 실제 페이지의 차이이며 사이트 장애를 의미하지 않습니다. 앞선 네트워크·임시 폴더 권한 오류 기록도 보존합니다. 이 사이트는 문서 예제용이므로 정기 모니터링 대상으로 사용하지 않습니다.

프로젝트의 **설정 → 프로젝트 삭제 → 삭제 확인**에서 요구사항·테스트·실행 기록·DB 보고서를 함께 삭제합니다. 실행 중인 프로젝트는 삭제할 수 없습니다. 로컬 artifacts 증거 파일과 백업은 남습니다. 기본 로그인 데모도 삭제할 수 있으며 초기화 시 다시 생성되지 않습니다.

공개 사이트 검사 결과는 [실행 요약](docs/public-website-result.md)을 참고하세요. 새 설치에서 직접 등록·실행하려면 `.\.venv\Scripts\python.exe -m scripts.run_public_website_sample`을 사용합니다. 실제 외부 접속이 발생하며 실행 시점의 화면에 따라 결과가 달라질 수 있습니다.

`start_qa.cmd`와 `startqa.cmd` 모두 사용할 수 있습니다. 서버가 이미 켜져 있으면 기존 화면을 열고, 꺼져 있으면 시작한 뒤 브라우저를 엽니다. 코드 업데이트 후 import 오류가 나타나면 기존 QA 서버를 종료하고 다시 실행하세요.
