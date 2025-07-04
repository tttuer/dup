# settings.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    wehago_id: str
    wehago_password: str
    db_url: str
    secret_key: str
    redis_host: str
    redis_port: int
    redis_password: str
    slack_webhook_url: str

    class Config:
        env_file = ".env"  # .env 파일을 사용하도록 지정

# 싱글톤처럼 쓸 수 있게 바로 인스턴스를 만들어줌
settings = Settings()
