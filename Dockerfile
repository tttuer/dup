# 1. 베이스 이미지를 Microsoft의 공식 Playwright 최신 이미지로 변경
# 이 이미지에는 Python 3.12와 브라우저 실행에 필요한 모든 시스템 종속성이 포함되어 있습니다.
FROM mcr.microsoft.com/playwright/python:v1.53.0-noble

# 2. prebuilt uv 바이너리 복사 (기존 Dockerfile의 방식을 그대로 활용)
# 이 한 줄로 Playwright 이미지에 uv를 설치합니다.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 3. 환경변수 및 작업 디렉토리 설정 (기존과 동일)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# 4. pyproject.toml, uv.lock 복사 (기존과 동일)
COPY pyproject.toml uv.lock /app/
COPY .env .env

# 5. uv를 사용하여 종속성 설치 (기존과 동일)
# 이제 이 이미지에 uv가 있으므로 uv sync를 그대로 사용할 수 있습니다.
RUN uv sync

# 6. 애플리케이션 코드 복사 (기존과 동일)
COPY . /app

# 7. FastAPI 실행 (기존과 동일)
# uv sync로 생성된 가상 환경의 uvicorn을 실행합니다.
CMD [".venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
