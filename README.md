# 환경 세팅

## uv 설치

### 윈도우

```irm https://astral.sh/uv/install.ps1 | iex```

### 맥

```curl -Ls https://astral.sh/uv/install.sh | sh```

## 가상 환경, 디펜던시 설치

```uv sync```

## pyenv win(윈도우)

```
git clone https://github.com/pyenv-win/pyenv-win.git "$env:USERPROFILE\.pyenv"
[Environment]::SetEnvironmentVariable("Path", "$env:USERPROFILE\.pyenv\pyenv-win\bin;$env:USERPROFILE\.pyenv\pyenv-win\shims;$($env:Path)", "User")

```

powershell 재시작

```
pyenv --version
```

```
pyenv install 3.13

pyenv global 3.13
pyenv local 3.9.13  # 특정 폴더에서만 적용

```

```
uv venv .venv --python "C:\Users\yang\.pyenv\pyenv-win\versions\3.13.2\python.exe"
pyenv shell 3.13.2  # 또는 pyenv local 3.13.2
uv venv .venv

```

## mac

```
brew install pyenv
brew install uv

pyenv install 3.13.2
pyenv global 3.13.2   # 또는 pyenv local 3.13.2 (디렉토리 한정)

echo 'eval "$(pyenv init --path)"' >> ~/.zprofile
echo 'eval "$(pyenv init -)"' >> ~/.zshrc
exec zsh

uv venv .venv


```

# fastapi 실행

```uvicorn main:app```

# mongodb

```docker-compose up -d```

## dup database 생성
