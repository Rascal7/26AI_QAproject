# TestPilot — AI 웹 QA 자동화

생성형 AI가 요구사항과 **실제 페이지 구조**를 바탕으로 브라우저 테스트를 설계하고, 사람이 검토·승인한 테스트를 실제 브라우저(pytest + Playwright)로 실행한 뒤, 실패하면 원인이 테스트 쪽인지 제품 쪽인지 AI가 구분해 QA 보고서로 정리합니다. 로컬 Flask 로그인 데모와 SQLite, Streamlit 관리 화면으로 구성된 인공지능프로젝트 과목의 개인 프로젝트입니다.

- **설계·구조·AI 활용·일정:** [프로젝트 개요](PROJECT_OVERVIEW.md) · **기획 대비 변경점:** [기획서](AI_Web_QA_Project_Plan.md) 앞부분
- **AI 효과 측정:** [AI 기능 효과 측정](docs/ai-evaluation.md) · **검증 기록:** [VALIDATION.md](VALIDATION.md)
- GitHub: https://github.com/Rascal7/26AI_QAproject · Notion: https://www.notion.so/3eb65ab291e7815faa49c0bb80c996df
- 디자인: [Figma — QA Lab 프로젝트 워크스페이스](https://www.figma.com/design/XQCufmFAXFWQjHWfsjOf3S?node-id=5-625)

**측정 결과 요약:** AI가 만든 테스트를 수정 없이 실행했을 때 PASS 비율이 페이지 구조를 주지 않으면 43%, 시작 페이지 구조를 주면 93%, 이동 후 페이지 구조까지 주면 100%였습니다(각 30개). 실패 원인 분석은 테스트 문제 7건과 실제 제품 결함 18건을 모두 맞게 구분했습니다([상세](docs/ai-evaluation.md)).

## 주요 기능

- **프로젝트·요구사항 관리:** 웹페이지 URL 하나당 프로젝트 하나. 전체 요구사항·예외사항과 개별 요구사항, 태그·검색.
- **AI 테스트 생성:** 요구사항 + 요청 문장 + 대상 페이지(이동 후 페이지 포함)의 요소·선택자 → 브라우저 동작 단계. 생성된 선택자를 실제 페이지에서 확인해 보여줍니다.
- **검토·승인 후 실행:** 승인한 테스트만 실행합니다. 실행은 백그라운드에서 진행되고 진행률을 보여주며, 다른 화면으로 이동해도 계속됩니다.
- **AI 실패 원인 분석:** FAIL마다 테스트 정의 문제 / 제품 결함 / 실행 환경 문제를 구분하고 관찰 사실과 추정 원인을 나눠 보여줍니다.
- **로그인 데모와 DB 비정상 상황:** 기준 테스트 10개(로그인 5 + DB 상태 5)와 의도적 결함 버전 4종으로 결함 탐지를 검증합니다.
- **증거와 보고서:** 스크린샷·민감정보를 지운 trace·HTTP·세션·DB 상태를 남기고 마크다운 보고서를 만듭니다.

## 설치 (Windows)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

SQLite는 Python 기본 라이브러리라 별도 DB 서버가 필요 없습니다. 가상환경 활성화나 Node.js/npm 설치도 필요하지 않습니다. 개발 도구(ruff)까지 설치하려면 `requirements-dev.txt`를 사용합니다.

**OpenAI API 키 (사용자가 직접 설정):** `.env.example`을 `.env`로 복사해 `OPENAI_API_KEY`를 본인 키로 채우고 QA 앱을 다시 시작하세요. 키는 채팅에 보내거나 Git에 올리지 마세요. 결제·사용 한도와 사용 가능한 모델은 본인 계정에서 관리합니다. `OPENAI_MODEL` 기본값은 `gpt-4.1-mini`이며 Structured Outputs를 지원하는 모델을 쓰세요. 키가 없으면 AI 기능만 꺼지고 기준 테스트·실행·보고서는 그대로 사용할 수 있습니다.

## 실행

1. `start_demo.cmd` 더블클릭 → 로그인 데모 http://127.0.0.1:5000/login
2. `start_qa.cmd` 더블클릭 → QA 앱 http://127.0.0.1:8501

`start_qa.cmd`는 서버가 이미 켜져 있으면 기존 화면을 열고, 꺼져 있으면 시작한 뒤 브라우저를 엽니다(예전 별칭 `startqa.cmd`는 정리했습니다). 터미널을 닫으면 서버가 종료됩니다. 로그인 데모 계정은 기획서의 로컬 데모 계정(`qa.user@example.com` / `QaDemo!234`)이고, 로그인 후 홈 화면의 **로그아웃** 버튼으로 세션을 끝냅니다. `data/qa.db`는 앱을 처음 시작할 때 만들어지고, 기본 로그인 데모 프로젝트도 이때 생성됩니다. 개인 DB와 과거 실행 증거는 저장소에 포함되지 않습니다.

## 사용 방법

1. 대시보드에서 **새 프로젝트** → 이름과 웹페이지 URL 등록. 다른 URL은 새 프로젝트로 등록합니다.
2. **요구사항**에서 전체 요구사항·예외사항을 저장하고 개별 요구사항을 추가합니다. 안내 문구나 이동 경로(예: `/home`)를 적어 두면 AI가 더 정확한 테스트를 만듭니다.
3. **테스트**에서 요구사항을 고르고 테스트를 추가합니다.
   - **기본 테스트:** 페이지 접속, 요소 표시, 문구 확인, 클릭 후 이동, 입력 후 안내. 선택자(예: `#email`, `h1`)와 기대 문구를 페이지에 맞게 고쳐서 추가합니다.
   - **AI로 추가:** 원하는 테스트를 문장으로 요청합니다. 생성된 단계와 선택자 확인 결과를 검토·수정하고 **실행 단계와 선택자를 확인했습니다**를 체크한 뒤 추가합니다.
4. **실행**에서 전체 또는 요구사항별로 실행합니다. 진행률이 표시되며, 실행 중에도 다른 화면을 사용할 수 있습니다.
5. **실행 기록**에서 검사 결과·실패 분석·보고서 다운로드를 확인합니다.

실제 비밀번호는 테스트 단계에 저장하지 마세요. `.env`에 `QA_TEST_PASSWORD`를 설정하고 입력값에 `${QA_TEST_PASSWORD}`를 씁니다. 비밀번호 칸을 비우는 단계는 그대로 쓸 수 있습니다.

**프로젝트 삭제:** **설정 → 프로젝트 삭제 → 삭제 확인**에서 요구사항·테스트·실행 기록·보고서를 함께 삭제합니다. 실행 중인 프로젝트는 삭제할 수 없고, 로컬 artifacts 증거 파일과 백업은 남습니다. 기본 로그인 데모를 지웠다면 `.\.venv\Scripts\python.exe -m qa_system.runner --restore-demo`로 새 프로젝트 번호에 기준 테스트 10개와 함께 다시 만듭니다.

## AI 기능과 안전장치

**실행 범위:** AI 테스트는 정해진 브라우저 동작 8종(이동·입력·클릭·키 입력·HTTP/문구/요소/URL 확인)만 조합합니다. 임의 Python·JavaScript·SQL을 생성하거나 실행하지 않습니다. 프로젝트와 같은 사이트 안에서만 이동하고, 실행에는 시간 제한을 적용합니다. 각 테스트에는 결과 확인 단계가 하나 이상 있어야 합니다. DB 상태를 바꾸는 fixture는 로그인 데모에서만 지원합니다. 초기 버전에서 저장된 AI 데모 테스트는 표시된 고정 실행 코드로만 실행됩니다.

**페이지 구조 전달(기본 켜짐):** AI로 추가할 때 등록 URL을 브라우저로 열어 제목·입력창·버튼·링크·오류 안내 영역의 선택자를 읽어 AI에 전달합니다.
- 시작 페이지의 링크와 요구사항·요청 문장에 적힌 같은 사이트 경로(예: `/home`, `/welcome`)도 최대 5개까지 **조회만 해서** 이동 후 페이지 구조로 함께 전달합니다.
- 입력·제출은 하지 않고, 입력값도 읽지 않습니다. 로그아웃·삭제·탈퇴처럼 열기만 해도 상태가 바뀔 수 있는 링크는 열지 않습니다. 로그인이 필요해 다른 페이지로 넘어가는 경로는 "접근 제한"으로 표시합니다.
- API 키가 없는 별도 프로세스에서 같은 사이트 안에서만 동작합니다.
- 생성 후에는 각 선택자가 시작 페이지나 읽은 이동 후 페이지에서 정확히 1개 요소와 일치하는지 확인해 보여줍니다. 단계를 수정했다면 **선택자 다시 확인**을 누르세요. 로그인이 필요한 페이지의 요소는 읽지 못하므로 '찾지 못함'으로 표시될 수 있습니다.
- 페이지를 읽지 못하면 구조 없이 생성하고 선택자가 추정값이라는 경고를 표시합니다. 저장된 AI 테스트에는 구조 사용 여부(`page_context_used`)와 선택자 확인 결과(`selector_check`)가 남습니다.

**실패 원인 분석:** 실행 화면의 **실패하면 AI 원인 분석 실행**(API 키가 있으면 기본 켜짐)을 쓰면 FAIL마다 요구사항과 실행 증거를 AI에 보내 테스트 정의 문제·제품 결함·실행 환경 문제로 구분합니다. 관찰한 사실과 추정 원인을 나눠 보여주고 다운로드 보고서에도 덧붙입니다. 실행당 최대 10건이며, 실행 기록의 실패 분석 탭에서 나중에 실행할 수도 있습니다. 증거 파일 경로는 AI에 보내지 않습니다. AI는 기대 결과를 바꾸거나 PASS/FAIL을 정하지 않습니다.

**비밀 정보:** OpenAI API 키는 테스트 실행·페이지 읽기 프로세스에 전달하지 않습니다. AI 입력과 증거에서 비밀번호·해시·쿠키를 지웁니다.

## 판정과 저장 위치

- **PASS:** HTTP·화면·세션·DB가 기대와 일치. 예상한 401·403·503 응답도 PASS입니다.
- **FAIL:** 준비를 마친 뒤 확인 단계가 불일치. 버그 근거로 기록합니다.
- **ERROR:** 준비·실행 환경·코드 오류. 제품 결함과 커버리지 집계에서 뺍니다.

| 위치 | 내용 |
|---|---|
| `data/demo.db` | 수동 데모 사용자. 기존 데이터를 보존합니다. |
| `data/qa.db` | 프로젝트, 요구사항, 시나리오, 테스트, 실행 이력, 결과, 버그, AI 분석, 보고서 |
| `artifacts/<실행ID>/` | 보고서, pytest 로그, 스크린샷, 민감정보를 지운 Playwright trace, 실행 코드 |

스크린샷은 비밀번호 입력을 가립니다(일반 웹 테스트는 모든 입력창). trace는 DOM 스냅샷·소스·네트워크 본문을 보존하지 않고 호출 정보의 비밀번호·쿠키도 지웁니다. HTTP 상태·오류 코드 증거는 결과 JSON과 DB에 남습니다. 성공 직후 이동하는 페이지에서 Chromium이 응답 본문을 버릴 수 있어서, HTTP 상태는 브라우저에서, 실제 응답 JSON은 테스트 전용 서버 관찰자로 수집합니다. 응답 모킹이나 외부 검사 API는 쓰지 않습니다.

로그인 데모의 DB 기준 테스트는 테스트마다 새 SQLite DB·브라우저 컨텍스트·운영체제가 정한 포트의 서버를 쓰고 끝나면 정리합니다. 그래서 5000 포트의 수동 데모와 충돌하지 않습니다. 일반 웹 테스트는 등록 URL에 새 브라우저 컨텍스트로 접속합니다. `data/demo.db`와 `data/qa.db`는 자동으로 지우지 않습니다.

## 검증

```powershell
# 기준 10개 실행 + 결과 DB·증거·보고서 저장
.\.venv\Scripts\python.exe -m qa_system.runner
# 순서를 뒤집어 테스트 간 독립성 확인
.\.venv\Scripts\python.exe -m qa_system.runner --reverse
# 결함 실험: 각 실행에서 해당 DB 기준 1개가 FAIL이어야 정상 탐지
.\.venv\Scripts\python.exe -m qa_system.runner --variant skip_disabled
.\.venv\Scripts\python.exe -m qa_system.runner --variant skip_lock
.\.venv\Scripts\python.exe -m qa_system.runner --variant skip_revalidation
# 전체 자동 테스트 (QA DB에 저장하려면 runner 사용)
.\.venv\Scripts\python.exe -m pytest
```

GitHub Actions(`.github/workflows/tests.yml`)가 main에 푸시하거나 PR을 열 때마다 Windows에서 린트·포매터 검사와 전체 테스트(실제 Chromium 포함)를 실행합니다. 테스트는 OpenAI를 호출하지 않습니다.

공개 사이트 검사 예시는 [실행 요약](docs/public-website-result.md)에 있습니다. 직접 등록·실행하려면 `.\.venv\Scripts\python.exe -m scripts.run_public_website_sample`을 씁니다. 실제 외부 접속이 발생하고 실행 시점의 화면에 따라 결과가 달라질 수 있으며, 이 문서 예제용 사이트는 정기 모니터링 대상으로 쓰지 않습니다.

## AI 기능 효과 측정

```powershell
.\.venv\Scripts\python.exe -m experiments.ai_quality --reps 3
.\.venv\Scripts\python.exe -m experiments.triage_faults --reps 3
```

- `ai_quality`: 로그인 데모와 실험용 회원가입 페이지(`experiments/signup_fixture.html`, `data-testid` 없음)에서 시나리오 5개씩, 같은 요청을 **구조 없음 / 시작 페이지 구조 / 시작+이동 후 페이지 구조** 조건으로 AI에 보냅니다. 생성된 테스트는 수정 없이 형식 검사 → 선택자 확인 → QA 실행기로 실제 실행하고, FAIL마다 AI 실패 분석도 합니다(`--no-triage`로 생략). 일시적인 API 오류는 최대 3번 다시 시도합니다. 조건은 `--conditions`로 고를 수 있고, 시범 실행은 `--reps 1 --limit 2`입니다.
- `triage_faults`: 의도적 결함 버전의 FAIL을 결함 표시를 가린 채 분석해, AI가 실제 제품 결함을 제품 결함으로 구분하는지 확인합니다.
- 결과는 `experiments/results/`에 보고서(.md), 원자료(.json), 수동 판정용 CSV로 저장됩니다. 두 스크립트 모두 실제 OpenAI API를 호출하고(`ai_quality` 기본 90회 + FAIL 수), 임시 QA DB를 쓰므로 `data/qa.db`는 바뀌지 않습니다.

## 개발

- 코드 스타일은 `pyproject.toml`의 ruff 설정을 따릅니다. 커밋 전에 `.\.venv\Scripts\python.exe -m ruff format .`과 `.\.venv\Scripts\python.exe -m ruff check .`을 실행합니다.
- 문서 스크린샷(`docs/images/`)은 `.\.venv\Scripts\python.exe -m scripts.capture_ui_docs`로 다시 찍습니다(5000·8505 포트 사용, OpenAI 약 4회 호출).
- 화면 흐름 점검은 QA 앱을 켠 상태에서 `.\.venv\Scripts\python.exe scripts\check_stitch_design.py`로 합니다(대시보드 → 프로젝트 목록 → 요구사항 → 테스트 추가 창 → 실행 기록 → 보고서, 모바일 가로 넘침 확인). 다른 주소는 `QA_PREVIEW_URL`로 지정합니다. `QA_DB_PATH` 환경변수로 QA DB 위치를 바꿀 수 있습니다.
- 구현 참고: [OpenAI Structured Outputs 공식 문서](https://developers.openai.com/api/docs/guides/structured-outputs). 로컬 실행에 GitHub 계정은 필요하지 않습니다.

## 문제 해결

- **모든 테스트가 ERROR이고 오류에 설치 명령이 보임:** Chromium이 없습니다. `.\.venv\Scripts\python.exe -m playwright install chromium`을 실행하세요. Chromium을 받을 수 없는 PC에서는 `QA_BROWSER_CHANNEL=msedge`를 설정하면 설치된 Microsoft Edge로 실행합니다(QA 앱은 `.env`, 명령줄 runner는 환경변수, pytest는 `--browser-channel msedge`).
- **실행 기록이 계속 "실행 중":** 앱이 실행 도중 종료된 경우입니다. 실행 제한 시간이 지나면 다음 앱 시작이나 프로젝트 삭제 때 ERROR로 정리됩니다.
- **코드 업데이트 후 import 오류:** 켜져 있던 QA 서버를 종료하고 `start_qa.cmd`로 다시 실행하세요.
- **"페이지에 접속할 수 없습니다":** 대상 서버가 켜져 있는지 확인하세요. 로그인 데모는 `start_demo.cmd`로 켭니다.
