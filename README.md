# dup-backend

## 프로젝트 개요

`dup-backend`는 전표, 증빙 등 회계 관련 문서를 효율적으로 관리하고 동기화하기 위한 백엔드 시스템입니다. Wehago 서비스와 연동하여 전표 데이터를 자동으로 가져오고, 사용자는 그룹별로 파일을 관리하며 접근 권한을 제어할 수 있습니다.

## 주요 기능

-   **사용자 관리:** 회원가입, 로그인, 사용자 정보 수정 및 승인 상태 관리
-   **그룹 관리:** 그룹 생성, 수정, 삭제 및 사용자 권한 부여
-   **파일 관리:** 전표 및 증빙 자료(PDF, 이미지) 업로드, 조회, 수정, 삭제
-   **Wehago 연동:** Wehago 서비스의 전표 데이터 실시간 동기화
-   **실시간 알림:** WebSocket을 통해 데이터 동기화 상태 및 사용자 승인 대기 상태 실시간 전송

## 아키텍처

본 프로젝트는 계층형 아키텍처(Layered Architecture)를 따르며, 각 계층은 명확히 분리된 역할을 수행합니다.

-   **`interface`**: 외부 세계와의 접점을 담당합니다. FastAPI를 사용하여 API 엔드포인트를 정의하고, 사용자의 요청을 받아 `application` 계층으로 전달합니다.
-   **`application`**: 비즈니스 로직을 처리하는 핵심 계층입니다. 사용자 요청을 받아 도메인 모델을 활용하여 실제 비즈니스 규칙을 수행하고, `infra` 계층의 리포지토리를 통해 데이터를 조작합니다.
-   **`domain`**: 애플리케이션의 핵심 도메인 모델과 비즈니스 규칙을 정의합니다. 순수한 데이터 구조와 행위를 포함하며, 다른 계층에 대한 의존성이 없습니다.
-   **`infra`**: 데이터베이스, 외부 API 등 외부 시스템과의 연동을 담당합니다. `domain` 계층에서 정의한 리포지토리 인터페이스를 구현하고, 실제 데이터베이스(MongoDB)와 상호작용합니다.

## API Endpoints

### Users

-   `POST /users`: (관리자) 신규 사용자 생성
-   `POST /users/signup`: 사용자 회원가입
-   `POST /users/login`: 로그인
-   `POST /users/refresh`: Access Token 갱신
-   `POST /users/logout`: 로그아웃
-   `GET /users`: 전체 사용자 목록 조회
-   `PATCH /users/{user_id}`: 사용자 정보 수정
-   `PATCH /users/{user_id}/approval`: (관리자) 사용자 승인/거절
-   `GET /users/pending`: (관리자) 승인 대기 중인 사용자 목록 조회

### Groups

-   `POST /groups`: 그룹 생성
-   `GET /groups`: 소속된 그룹 목록 조회
-   `GET /groups/{id}`: 특정 그룹 정보 조회
-   `PUT /groups/{id}`: 그룹 정보 수정
-   `DELETE /groups/{id}`: 그룹 삭제
-   `PATCH /groups/{id}`: 그룹에 사용자 권한 부여

### Files

-   `POST /files`: 파일 업로드
-   `GET /files`: 파일 목록 조회
-.  `GET /files/{id}`: 특정 파일 정보 조회
-   `PUT /files/{id}`: 파일 정보 수정
-   `DELETE /files/{id}`: 파일 삭제
-   `DELETE /files`: 다중 파일 삭제

### Vouchers

-   `POST /vouchers/sync`: Wehago 전표 데이터 동기화
-   `GET /vouchers`: 전표 목록 조회
-   `GET /vouchers/{id}`: 특정 전표 정보 조회
-   `PATCH /vouchers/{id}`: 전표 정보 수정 (파일 연결)
-   `DELETE /vouchers/{id}`: 전표 삭제
-   `DELETE /vouchers`: 다중 전표 삭제

### WebSocket

-   `WS /api/ws/sync-status`: 전표 동기화 상태 실시간 알림
-   `WS /api/ws/pending-users`: 승인 대기 사용자 수 실시간 알림

## 환경 변수

프로젝트 실행을 위해 `.env` 파일을 생성하고 다음 환경 변수를 설정해야 합니다.

```
WEHAGO_ID=your_wehago_id
WEHAGO_PASSWORD=your_wehago_password
DB_URL=your_mongodb_connection_string
SECRET_KEY=your_jwt_secret_key
REDIS_HOST=your_redis_host
REDIS_PORT=your_redis_port
REDIS_PASSWORD=your_redis_password
SLACK_WEBHOOK_URL=your_slack_webhook_url
# 납부 업무 외부 연동 (설정하지 않으면 연동은 비활성화됩니다)
GOOGLE_CALENDAR_ID=your_google_calendar_id
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
FRONTEND_BASE_URL=https://arc.baeksung.kr
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
PAYMENT_SUMMARY_HOUR=8
PAYMENT_SUMMARY_MINUTE=30
```

### 납부 업무 구글 캘린더와 노션 캘린더 연결

노션 캘린더 앱은 별도 노션 데이터베이스 없이도 연결된 구글 캘린더 일정을 보여 줄 수 있습니다. DUP는 납부일이 있는 업무마다 구글 캘린더에 하루 종일 일정을 만들고, 일정의 설명에는 DUP 업무 화면으로 바로 가는 주소만 넣습니다. 금액, 설명, 계좌번호, 요청·증빙 첨부파일은 구글 캘린더와 텔레그램으로 보내지 않습니다.

#### 최초 1회 설정

1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트를 만들고 **Google Calendar API**를 사용 설정한다.
2. **서비스 계정**을 만들고 JSON 키를 내려받는다. JSON 파일 안의 `client_email`이 자동화용 구글 계정 주소다.
3. 일정을 넣을 구글 캘린더의 **설정 및 공유 → 특정 사용자 또는 그룹과 공유**에서 그 `client_email`을 추가하고 권한을 **일정 변경**으로 준다.
4. 같은 캘린더의 **통합 → 캘린더 ID**를 복사한다.
5. 노션 캘린더 앱에서 그 구글 계정을 연결하고, 방금 공유한 캘린더가 보이게 선택한다.

#### GitHub `ENV_VARS`에 넣을 값

GitHub 저장소의 **Settings → Environments → Production → Secrets → `ENV_VARS`**에 기존 값 아래 두 줄을 추가한다. 서비스 계정 JSON은 반드시 한 줄이어야 한다.

```text
GOOGLE_CALENDAR_ID=복사한-캘린더-ID
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account",...한-줄-전체-JSON...}
```

다운받은 JSON 파일을 한 줄로 만들 때는 PowerShell에서 아래 명령을 쓴다. 출력된 한 줄 전체를 `GOOGLE_SERVICE_ACCOUNT_JSON=` 뒤에 붙여 넣는다.

```powershell
(Get-Content -Raw .\google-service-account.json | ConvertFrom-Json | ConvertTo-Json -Compress)
```

### 운영 환경 비밀값 관리

운영 비밀값은 GitHub Environment의 `ENV_VARS` 하나에만 보관한다. 배포할 때 GitHub Actions가 이를 Kubernetes `dup-env` Secret으로 바꾸고, 서버에 적용한다. `.env`와 변환된 `k8s/dup-env.yaml`은 Docker 이미지와 Git에 들어가지 않는다.

환경변수를 추가하거나 바꿀 때는 `ENV_VARS`의 해당 줄만 고치고 `main`에 배포하면 된다. 값은 `KEY=VALUE` 형식이며, `=`가 값에 들어가도 그대로 사용할 수 있다. `GOOGLE_SERVICE_ACCOUNT_JSON`처럼 긴 JSON도 한 줄로 넣으면 된다.

## 로컬 개발 환경 설정

### 1. uv 설치

**Windows**

```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

**macOS/Linux**

```bash
curl -Ls https://astral.sh/uv/install.sh | sh
```

### 2. Python 버전 관리 (pyenv)

**Windows (pyenv-win)**

```powershell
git clone https://github.com/pyenv-win/pyenv-win.git "$env:USERPROFILE\.pyenv"
[Environment]::SetEnvironmentVariable("Path", "$env:USERPROFILE\.pyenv\pyenv-win\bin;$env:USERPROFILE\.pyenv\pyenv-win\shims;$($env:Path)", "User")
```

PowerShell을 재시작한 후, 원하는 Python 버전을 설치하고 설정합니다.

```powershell
pyenv install 3.13
pyenv global 3.13
```

**macOS/Linux**

```bash
brew install pyenv
pyenv install 3.13
pyenv global 3.13
```

### 3. 가상 환경 및 의존성 설치

```bash
uv venv .venv
uv sync
```

## Docker를 이용한 실행

`docker-compose.yml` 파일을 사용하여 MongoDB, Redis 및 FastAPI 애플리케이션을 한 번에 실행할 수 있습니다.

### 1. Docker 이미지 빌드

```bash
docker-compose build
```

### 2. Docker 컨테이너 실행

```bash
docker-compose up -d
```

## 애플리케이션 실행

### FastAPI 서버 실행

```bash
uvicorn main:app --reload
```

### 데이터베이스 초기화

애플리케이션 실행 후, `dup` 데이터베이스를 MongoDB에 생성해야 합니다.
