# utils/slack.py
import aiohttp
from utils.settings import settings
from utils.logger import logger
from common.exceptions import InternalServerError

async def send_slack_message(text: str):
    webhook_url = settings.slack_webhook_url
    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL is not set")
        return

    payload = {"text": text}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as response:
                if response.status != 200:
                    response_text = await response.text()
                    raise InternalServerError(f"슬랙 전송 실패: {response.status}, {response_text}")
    except Exception as e:
        raise InternalServerError(f"슬랙 예외 발생: {e}")

async def send_signup_notification(user_id: str, name: str = None):
    display_name = name if name else user_id
    text = f"🔔 새로운 회원가입 요청이 있습니다\n사용자 ID: {user_id}\n이름: {display_name}\n승인이 필요합니다."
    await send_slack_message(text)
