# 1. Python 3.12 베이스 이미지
FROM python:3.12-slim

# 2. 환경 변수 설정
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. 작업 디렉토리
WORKDIR /app

# 4. 필요한 시스템 패키지 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 5. uv 설치 (패키지 매니저)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# 6. pyproject.toml, uv.lock 복사
COPY pyproject.toml uv.lock /app/

# 7. 패키지 설치
RUN ~/.cargo/bin/uv sync --system --no-cache

# 8. 애플리케이션 복사
COPY . /app

# 9. FastAPI 실행
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
