# 1. Python 베이스 이미지
FROM python:3.13-slim-bookworm

# 2. prebuilt uv 바이너리 복사 (FROM 공식 이미지)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 3. 환경변수
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# 4. 시스템 패키지 설치 (필요시 최소화 가능)
RUN apt-get update && apt-get install -y --no-install-recommends && apt-get install -y curl \
    build-essential \
    gcc \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# 5. pyproject.toml, uv.lock 복사
COPY pyproject.toml uv.lock /app/
COPY .env .env



# 6. 패키지 설치
RUN uv sync

# 7. 애플리케이션 코드 복사
COPY . /app

# 8. FastAPI 실행
CMD [".venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
