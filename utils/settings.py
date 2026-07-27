# settings.py
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    wehago_id: str
    wehago_password: str
    db_url: str
    secret_key: str
    redis_host: str
    redis_port: int
    redis_password: str
    slack_webhook_url: str
    notion_api_token: Optional[str] = None
    notion_payment_database_id: Optional[str] = None
    frontend_base_url: str = "https://arc.baeksung.kr"
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    payment_summary_hour: int = 8
    payment_summary_minute: int = 30

    class Config:
        env_file = ".env"  # .env 파일을 사용하도록 지정

# 싱글톤처럼 쓸 수 있게 바로 인스턴스를 만들어줌
settings = Settings()
