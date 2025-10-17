# --- 1단계: Builder ---
# 종속성을 설치하고 가상 환경을 만드는 빌더 스테이지
FROM mcr.microsoft.com/playwright/python:v1.54.0-noble AS builder

# uv 설치
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# 가상 환경 생성
# --no-cache 옵션으로 캐시를 남기지 않아 빌드 최적화
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-cache

# --- 2단계: Final ---
# 최종적으로 사용할 경량화된 이미지 스테이지
FROM mcr.microsoft.com/playwright/python:v1.54.0-noble

# 브라우저 실행을 위해 root 사용자 유지 (보안보다 기능 우선)
# USER pwuser

WORKDIR /app

# Builder 스테이지에서 생성한 가상 환경만 복사
COPY --from=builder /app/.venv ./.venv

# 애플리케이션 코드 복사
COPY . .

# 불필요한 브라우저(Firefox, WebKit) 삭제하여 용량 확보
RUN rm -rf /ms-playwright/firefox-* && \
    rm -rf /ms-playwright/webkit-* \

# 가상 환경의 경로를 PATH에 추가
ENV PATH="/app/.venv/bin:$PATH"

# FastAPI 실행
CMD ["/app/.venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]