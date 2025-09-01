# utils/slack.py
import requests
from utils.settings import settings
from utils.logger import logger
from common.exceptions import InternalServerError

def send_slack_message(text: str):
    webhook_url = settings.slack_webhook_url
    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL is not set")
        return

    payload = {"text": text}

    try:
        response = requests.post(webhook_url, json=payload)
        if response.status_code != 200:
            raise InternalServerError(f"슬랙 전송 실패: {response.status_code}, {response.text}")
    except Exception as e:
        raise InternalServerError(f"슬랙 예외 발생: {e}")
