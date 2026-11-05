"""네이버 받은메일함에서 이번 요청 이후 도착한 위하고 인증 메일만 읽는다."""
import asyncio
import imaplib
import re
import ssl
from contextlib import contextmanager
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr
from html.parser import HTMLParser

from utils.settings import settings

SUBJECT = "[WEHAGO] 로그인 인증 코드를 확인해주세요"


class MailText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1
        elif tag in ("br", "p", "div", "td", "tr"):
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)
        elif tag in ("p", "div", "td", "tr"):
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def is_auth_mail(message):
    return (
        parseaddr(str(message.get("From", "")))[1].lower() == "no-reply@wehago.com"
        and " ".join(str(message.get("Subject", "")).split()) == SUBJECT
    )


def extract_code(raw):
    message = BytesParser(policy=policy.default).parsebytes(raw)
    if not is_auth_mail(message):
        return None
    body = message.get_body(preferencelist=("plain", "html"))
    if body is None:
        return None
    text = body.get_content()
    if body.get_content_subtype() == "html":
        parser = MailText()
        parser.feed(text)
        text = "".join(parser.parts)
    # 숫자 여섯 개가 각각 다른 HTML 요소에 있어도 읽는다. 여러 후보는 사용하지 않는다.
    codes = set(re.findall(r"(?<!\d)(\d(?:\s*\d){5})(?!\s*\d)", text))
    codes = {re.sub(r"\s", "", code) for code in codes}
    return codes.pop() if len(codes) == 1 else None


class NaverEmailReader:
    def __init__(self):
        self.baseline = None

    @staticmethod
    def configured():
        return bool(settings.wehago_mail_username and settings.wehago_mail_app_password)

    @contextmanager
    def connect(self):
        client = imaplib.IMAP4_SSL("imap.naver.com", 993,
                                  ssl_context=ssl.create_default_context(), timeout=10)
        try:
            password = settings.wehago_mail_app_password.get_secret_value()
            client.login(settings.wehago_mail_username, password)
            status, _ = client.select("INBOX", readonly=True)
            if status != "OK":
                raise ValueError("받은메일함 연결 실패")
            yield client
        finally:
            try:
                client.logout()
            except (OSError, imaplib.IMAP4.error):
                pass

    @staticmethod
    def mailbox_number(client, name):
        _, values = client.response(name)
        if not values or not values[0]:
            raise ValueError("메일함 식별 정보 누락")
        return int(values[0])

    def prepare(self):
        with self.connect() as client:
            self.baseline = (self.mailbox_number(client, "UIDVALIDITY"),
                             self.mailbox_number(client, "UIDNEXT"))

    @staticmethod
    def fetch_bytes(client, uid, query):
        status, data = client.uid("fetch", uid, query)
        if status != "OK":
            raise ValueError("메일 조회 실패")
        return next((part[1] for part in data if isinstance(part, tuple)), b"")

    def find_code(self):
        if self.baseline is None:
            return None
        validity, first_uid = self.baseline
        with self.connect() as client:
            if self.mailbox_number(client, "UIDVALIDITY") != validity:
                raise ValueError("메일함 식별 정보 변경")
            status, data = client.uid("search", None, "UID", f"{first_uid}:*")
            if status != "OK":
                raise ValueError("새 메일 조회 실패")
            # IMAP의 n:*는 n보다 큰 UID가 없을 때 마지막 옛 메일도 반환할 수 있다.
            uids = [uid for uid in data[0].split() if int(uid) >= first_uid]
            for uid in reversed(uids[-20:]):
                header = self.fetch_bytes(client, uid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
                message = BytesParser(policy=policy.default).parsebytes(header)
                if not is_auth_mail(message):
                    continue
                raw = self.fetch_bytes(client, uid, "(BODY.PEEK[])")
                code = extract_code(raw)
                if code:
                    return code
        return None

    async def wait_for_code(self):
        async with asyncio.timeout(60):
            while True:
                code = await asyncio.to_thread(self.find_code)
                if code:
                    return code
                await asyncio.sleep(3)
