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
NOTION_API_TOKEN=your_notion_integration_token
NOTION_PAYMENT_DATABASE_ID=your_notion_database_id
FRONTEND_BASE_URL=https://arc.baeksung.kr
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
PAYMENT_SUMMARY_HOUR=8
PAYMENT_SUMMARY_MINUTE=30
```

### 납부 업무 노션 데이터베이스

노션에서 `DUP 납부 일정` 데이터베이스를 만들고, 해당 데이터베이스를 연동에 공유해야 합니다. 속성 이름과 종류는 아래처럼 정확히 맞춰야 합니다.

| 속성 | 종류 |
| --- | --- |
| 업무명 | 제목 |
| 납부일 | 날짜 |
| 상태 | 선택 (`기한 미설정`, `납부 대기`, `기한 초과`, `완료`) |
| 담당자 | 텍스트 |
| DUP에서 확인 | URL |
| DUP 업무 ID | 텍스트 |
| 마지막 동기화 | 날짜 |

연동은 DUP에서 노션으로만 데이터를 보냅니다. 금액, 설명, 계좌번호, 요청·증빙 첨부파일은 노션과 텔레그램으로 전송하지 않습니다.

### 운영 환경 비밀값 관리

운영 비밀값은 `.env` 파일을 Docker 이미지에 포함하지 않고, 암호화된 `k8s/dup-env.sops.yaml` 파일에서 Kubernetes Secret으로 배포합니다.

#### 최초 1회 전환

1. `age`로 만든 `age.key` 파일을 안전한 비밀번호 관리자에 백업한다. 이 파일을 잃으면 암호화된 운영 비밀값을 열 수 없다.
2. GitHub 저장소의 **Settings → Environments → Production → Secrets**에 `SOPS_AGE_KEY`를 만든다. 값은 `age.key` 파일의 전체 내용이다.

   ```powershell
   Get-Content -Raw age.key | gh secret set SOPS_AGE_KEY --env Production
   ```

3. `SOPS 비밀값 최초 변환` GitHub Actions 워크플로우를 수동 실행한다. 이 워크플로우는 기존 `ENV_VARS`를 읽어 `k8s/dup-env.sops.yaml`로 암호화해 커밋한다.
4. `Deploy to Kubernetes` 워크플로우를 수동 실행한다. 이때 암호화 파일을 복호화해 K3s의 `dup-env` Secret으로 적용한다.
5. 서비스가 정상 동작하는 것을 확인한 뒤에만 기존 GitHub `ENV_VARS` 시크릿을 삭제한다.

`ENV_VARS`는 암호화 파일이 만들어지기 전 첫 배포를 위한 호환용이다. 전환이 끝난 뒤에는 새 환경변수를 추가할 때 GitHub 시크릿을 수정하지 않는다.

#### 평소 환경변수 추가·수정

1. SOPS를 한 번만 설치한다.

   ```powershell
   winget install -e --id Mozilla.SOPS
   ```

2. 현재 PowerShell에 복호화 키 파일 위치를 알려준다.

   ```powershell
   $env:SOPS_AGE_KEY_FILE = (Resolve-Path .\age.key)
   ```

3. 암호화된 운영 설정을 연다.

   ```powershell
   sops k8s/dup-env.sops.yaml
   ```

4. `stringData` 아래에 값을 추가하거나 수정한 뒤 저장하고 편집기를 닫는다. 예를 들어 노션·텔레그램 연동을 켤 때는 다음처럼 추가한다.

   ```yaml
   stringData:
     NOTION_API_TOKEN: 실제-노션-토큰
     NOTION_PAYMENT_DATABASE_ID: 실제-데이터베이스-ID
     FRONTEND_BASE_URL: https://arc.baeksung.kr
     TELEGRAM_BOT_TOKEN: 실제-텔레그램-봇-토큰
     TELEGRAM_CHAT_ID: 실제-채팅방-ID
   ```

5. 암호화된 파일만 커밋하고 `main`에 병합한다. 배포 워크플로우가 자동으로 K3s Secret과 DUP Pod를 갱신한다.

   ```powershell
   git add k8s/dup-env.sops.yaml
   git commit -m "운영 환경변수 수정"
   git push
   ```

#### 꼭 지킬 것

- `age.key`와 `AGE-SECRET-KEY-1...` 값은 Git, 채팅, 문서에 올리지 않는다.
- `k8s/dup-env.sops.yaml`은 Git에 올려도 되지만, `k8s/dup-env.yaml` 같은 복호화된 파일은 올리면 안 된다.
- `.gitignore`가 `age.key`와 복호화된 파일을 제외한다. 그래도 `git status`로 커밋 전 확인한다.
- 새 설정값은 가능하면 기본값을 둬서, 기능을 켜기 전까지 배포가 실패하지 않게 만든다.

실제 값은 암호화되어 GitHub에 저장되며, `age.key` 또는 GitHub의 `SOPS_AGE_KEY` 없이는 읽을 수 없다.

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
