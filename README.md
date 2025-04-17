# 환경 세팅

## uv 설치

### 윈도우

irm https://astral.sh/uv/install.ps1 | iex

### 맥

curl -Ls https://astral.sh/uv/install.sh | sh

## 가상 환경, 디펜던시 설치

uv sync

# fastapi 실행

uvicorn main:app

# mongodb

docker-compose up -d

## dup database 생성
