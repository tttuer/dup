"""텔레그램의 이번 인증 요청에 답장한 번호만 위하고에 전달한다."""
import asyncio
import re
from contextlib import asynccontextmanager
from uuid import uuid4

import aiohttp
from redis.asyncio import Redis

from common.exceptions import LoginError
from utils.logger import logger
from utils.settings import settings
from utils.naver_email import NaverEmailReader

WAIT_SECONDS = 240
LOCK_KEY = "wehago:telegram:email-auth"


class TelegramEmailAuth:
    def __init__(self):
        self.session = None
        self.mailbox = None
        self.reply_seconds = WAIT_SECONDS

    async def call(self, method, **payload):
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}"
        try:
            async with self.session.post(url, json=payload) as response:
                data = await response.json()
                if response.status != 200 or not data.get("ok"):
                    raise LoginError("텔레그램 인증 통신에 실패했습니다. 봇 연결 상태를 확인해주세요.", status_code=502)
                return data["result"]
        except (aiohttp.ClientError, asyncio.TimeoutError):
            # 예외 문자열에는 봇 토큰이 포함될 수 있으므로 기록하지 않는다.
            raise LoginError("텔레그램 인증 연결이 끊겼습니다. 동기화를 다시 시작해주세요.", status_code=502) from None

    async def send(self, text, **extra):
        return await self.call("sendMessage", chat_id=settings.telegram_chat_id, text=text, **extra)

    async def notify(self, text):
        if not (settings.telegram_bot_token and settings.telegram_chat_id):
            return
        try:
            await self.send(text)
        except Exception:
            logger.warning("위하고 텔레그램 인증 결과 알림 발송 실패")

    async def prepare_mailbox(self):
        if not NaverEmailReader.configured():
            return
        try:
            mailbox = NaverEmailReader()
            await asyncio.to_thread(mailbox.prepare)
            self.mailbox = mailbox
        except Exception:
            logger.warning("네이버 메일 연결 실패. 텔레그램 인증으로 전환합니다.")

    async def wait_for_code(self):
        if self.mailbox is not None:
            started = asyncio.get_running_loop().time()
            try:
                code = await self.mailbox.wait_for_code()
                logger.info("새 위하고 인증 메일에서 번호를 확인했습니다.")
                return code
            except Exception:
                logger.warning("새 위하고 인증 메일 확인 실패. 텔레그램 인증으로 전환합니다.")
                elapsed = asyncio.get_running_loop().time() - started
                self.reply_seconds = max(1, int(WAIT_SECONDS - elapsed))
        if not (settings.telegram_bot_token and settings.telegram_chat_id):
            raise LoginError("메일 자동 인증에 실패했습니다. 네이버 메일 또는 텔레그램 설정을 확인해주세요.", status_code=503)
        return await self.wait_for_telegram_code()

    async def wait_for_telegram_code(self):
        info = await self.call("getWebhookInfo")
        if info.get("url"):
            raise LoginError("이 텔레그램 봇은 다른 수신 연결을 사용 중입니다. 인증 전용 봇을 설정해주세요.", status_code=503)
        chat = await self.call("getChat", chat_id=settings.telegram_chat_id)
        if chat.get("type") != "private":
            raise LoginError("이메일 인증은 텔레그램 봇과의 개인 대화방을 설정해주세요.", status_code=503)
        prompt = await self.send(
            "🔐 위하고 로그인에 이메일 인증이 필요합니다.\n"
            "이메일로 받은 6자리 번호를 이 메시지에 ‘답장’해주세요.\n"
            f"{self.reply_seconds}초 이내에 답장하면 자동 동기화를 계속합니다.",
            reply_markup={"force_reply": True, "input_field_placeholder": "이메일 인증 번호 6자리"},
        )
        offset = None
        try:
            async with asyncio.timeout(self.reply_seconds):
                while True:
                    payload = {"timeout": 20, "allowed_updates": ["message"]}
                    if offset is not None:
                        payload["offset"] = offset
                    updates = await self.call("getUpdates", **payload)
                    for update in updates:
                        offset = update["update_id"] + 1
                        message = update.get("message", {})
                        if not self.matches_reply(message, prompt):
                            continue
                        code = message.get("text", "").strip()
                        if re.fullmatch(r"[0-9]{6}", code):
                            await self.notify("인증 번호를 받았습니다. 위하고 로그인을 확인하고 있습니다.")
                            return code
                        await self.notify("인증 번호는 숫자 6자리입니다. 인증 요청 메시지에 다시 답장해주세요.")
        except TimeoutError:
            await self.notify("⌛ 위하고 이메일 인증 시간이 지났습니다. 이번 동기화를 종료합니다. 동기화를 다시 시작해주세요.")
            raise LoginError("이메일 인증 시간이 만료되었습니다.", status_code=408) from None

    @staticmethod
    def matches_reply(message, prompt):
        return (
            str(message.get("chat", {}).get("id")) == str(settings.telegram_chat_id)
            and str(message.get("from", {}).get("id")) == str(settings.telegram_chat_id)
            and not message.get("from", {}).get("is_bot", False)
            and message.get("reply_to_message", {}).get("message_id") == prompt["message_id"]
            and message.get("date", 0) >= prompt["date"]
        )


@asynccontextmanager
async def email_auth_session():
    if not (NaverEmailReader.configured() or (settings.telegram_bot_token and settings.telegram_chat_id)):
        raise LoginError("네이버 메일 또는 텔레그램 인증 설정이 필요합니다.", status_code=503)
    owner = uuid4().hex
    async with Redis(host=settings.redis_host, port=settings.redis_port,
                     password=settings.redis_password) as redis:
        # 여러 서버가 같은 봇의 답장을 동시에 가져가지 않도록 한다.
        if not await redis.set(LOCK_KEY, owner, nx=True, ex=360):
            raise LoginError("다른 위하고 이메일 인증이 진행 중입니다. 잠시 후 다시 시도해주세요.", status_code=409)
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                auth = TelegramEmailAuth()
                auth.session = session
                yield auth
        finally:
            await redis.eval(
                "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end",
                1, LOCK_KEY, owner,
            )
