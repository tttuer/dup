import asyncio
import os
import unittest
from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

test_settings = {name: "test" for name in (
    "WEHAGO_ID", "WEHAGO_PASSWORD", "WEHAGO_BAEKSUNG_URL", "WEHAGO_PYEONGTAEK_URL",
    "WEHAGO_PARAN_URL", "WEHAGO_PYEONGTAEK_MAUL_URL", "WEHAGO_BAEKSUNG_PYEONGTAEK_BRANCH_URL",
    "DB_URL", "SECRET_KEY", "REDIS_HOST", "REDIS_PASSWORD", "SLACK_WEBHOOK_URL",
)}
test_settings.update(REDIS_PORT="6379")
with patch.dict(os.environ, test_settings):
    from utils.wehago_email_auth import TelegramEmailAuth
from common.exceptions import LoginError
from utils.whg import Whg


class TelegramEmailAuthTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.auth = TelegramEmailAuth()
        self.prompt = {"message_id": 50, "date": 100}
        self.reply = {"chat": {"id": 123}, "from": {"id": 123},
                      "reply_to_message": {"message_id": 50}, "date": 101, "text": "012345"}
        self.setting_patch = patch("utils.wehago_email_auth.settings.telegram_chat_id", "123")
        self.setting_patch.start()
        self.addCleanup(self.setting_patch.stop)
        token_patch = patch("utils.wehago_email_auth.settings.telegram_bot_token", "dummy")
        token_patch.start()
        self.addCleanup(token_patch.stop)

    def test_only_current_reply_from_configured_person_is_accepted(self):
        self.assertTrue(self.auth.matches_reply(self.reply, self.prompt))
        for field, value in (
            ("chat", {"id": 999}), ("from", {"id": 999}),
            ("from", {"id": 123, "is_bot": True}),
            ("reply_to_message", {"message_id": 49}), ("date", 99),
        ):
            reply = deepcopy(self.reply)
            reply[field] = value
            self.assertFalse(self.auth.matches_reply(reply, self.prompt), field)

    async def test_invalid_code_ignored_and_leading_zero_preserved(self):
        invalid = dict(self.reply, text="12345")
        self.auth.call = AsyncMock(side_effect=[
            {"url": ""}, {"type": "private"},
            [{"update_id": 1, "message": invalid}],
            [{"update_id": 2, "message": self.reply}],
        ])
        self.auth.send = AsyncMock(return_value=self.prompt)
        self.assertEqual(await self.auth.wait_for_telegram_code(), "012345")
        self.assertEqual(self.auth.call.await_args.kwargs["offset"], 2)

    async def test_existing_webhook_is_not_replaced(self):
        self.auth.call = AsyncMock(return_value={"url": "https://existing.example"})
        self.auth.send = AsyncMock()
        with self.assertRaises(LoginError) as error:
            await self.auth.wait_for_telegram_code()
        self.assertEqual(error.exception.status_code, 503)
        self.auth.send.assert_not_awaited()

    async def test_group_chat_is_rejected(self):
        self.auth.call = AsyncMock(side_effect=[{"url": ""}, {"type": "group"}])
        self.auth.send = AsyncMock()
        with self.assertRaises(LoginError):
            await self.auth.wait_for_telegram_code()
        self.auth.send.assert_not_awaited()

    async def test_timeout_reports_expiration(self):
        async def slow_updates(method, **kwargs):
            if method == "getWebhookInfo":
                return {"url": ""}
            if method == "getChat":
                return {"type": "private"}
            await asyncio.sleep(1)
        self.auth.call = AsyncMock(side_effect=slow_updates)
        self.auth.send = AsyncMock(return_value=self.prompt)
        self.auth.reply_seconds = 0.01
        with patch("utils.wehago_email_auth.WAIT_SECONDS", 0.01):
            with self.assertRaises(LoginError) as error:
                await self.auth.wait_for_telegram_code()
        self.assertEqual(error.exception.status_code, 408)
        self.assertIn("시간이 지났습니다", self.auth.send.await_args.args[0])


class LoginEmailAuthTest(unittest.IsolatedAsyncioTestCase):
    def page(self, *, logged_in=False, email_open=False, count=6):
        page = MagicMock()
        main = MagicMock(first=MagicMock(wait_for=AsyncMock()))
        main.is_visible = AsyncMock(return_value=logged_in)
        main.wait_for = AsyncMock()
        duplicate = MagicMock(first=MagicMock(wait_for=AsyncMock()))
        duplicate.is_visible = AsyncMock(return_value=False)
        button = MagicMock(first=MagicMock(wait_for=AsyncMock(), click=AsyncMock()))
        heading = MagicMock(first=MagicMock(wait_for=AsyncMock()))
        heading.is_visible = AsyncMock(return_value=email_open)
        heading.wait_for = AsyncMock()
        fields = MagicMock()
        fields.count = AsyncMock(return_value=count)
        fields.fill = AsyncMock()
        digits = [MagicMock(fill=AsyncMock()) for _ in range(6)]
        fields.nth.side_effect = lambda i: digits[i]
        page.locator.side_effect = lambda selector: {
            ".snbnext": main, ".duplicate_login": duplicate,
            'input:visible:not([type="hidden"])': fields,
        }[selector]
        page.get_by_text.side_effect = lambda text, **_: button if text == "이메일 인증" else heading
        page.get_by_role.return_value.click = AsyncMock()
        return page, digits, button, fields

    async def test_existing_login_does_not_request_telegram(self):
        page, _, _, _ = self.page(logged_in=True)
        with patch("utils.whg.email_auth_session") as session:
            await Whg()._complete_email_auth(page)
        session.assert_not_called()

    async def test_email_button_then_six_digits_then_verification(self):
        page, digits, button, _ = self.page()
        auth = MagicMock(prepare_mailbox=AsyncMock(), wait_for_code=AsyncMock(return_value="012345"), notify=AsyncMock())
        session = MagicMock()
        session.__aenter__ = AsyncMock(return_value=auth)
        session.__aexit__ = AsyncMock(return_value=False)
        with patch("utils.whg.email_auth_session", return_value=session), \
             patch.object(Whg, "_handle_duplicate_login", new=AsyncMock()):
            await Whg()._complete_email_auth(page)
        button.first.click.assert_awaited_once()
        for digit, value in zip(digits, "012345"):
            digit.fill.assert_awaited_once_with(value)
        page.get_by_role.return_value.click.assert_awaited_once()
        self.assertIn("완료", auth.notify.await_args.args[0])

    async def test_failed_verification_reports_failure(self):
        page, _, _, _ = self.page(email_open=True)
        page.get_by_role.return_value.click.side_effect = RuntimeError("실패")
        auth = MagicMock(prepare_mailbox=AsyncMock(), wait_for_code=AsyncMock(return_value="012345"), notify=AsyncMock())
        session = MagicMock()
        session.__aenter__ = AsyncMock(return_value=auth)
        session.__aexit__ = AsyncMock(return_value=False)
        with patch("utils.whg.email_auth_session", return_value=session):
            with self.assertRaises(LoginError) as error:
                await Whg()._complete_email_auth(page)
        self.assertEqual(error.exception.status_code, 422)
        self.assertIn("실패", auth.notify.await_args.args[0])


from email.message import EmailMessage
from pydantic import SecretStr
from utils.naver_email import NaverEmailReader, extract_code, SUBJECT


class NaverEmailTest(unittest.TestCase):
    def mail(self, text="인증 코드 0 7 4 2 0 0", sender="no-reply@wehago.com", subject=SUBJECT, html=False):
        message = EmailMessage()
        message["From"] = sender
        message["Subject"] = subject
        message.set_content(text, subtype="html" if html else "plain")
        return message.as_bytes()

    def test_spaced_digits_preserve_leading_zero(self):
        self.assertEqual(extract_code(self.mail()), "074200")

    def test_html_digits_and_style_are_handled(self):
        raw = self.mail('<style>.x {color:#123456}</style><p>인증 코드</p>'
                        '<table><tr>' + ''.join(f'<td>{d}</td>' for d in '012345') + '</tr></table>', html=True)
        self.assertEqual(extract_code(raw), "012345")

    def test_unrelated_sender_subject_and_ambiguous_codes_are_ignored(self):
        self.assertIsNone(extract_code(self.mail(sender="other@example.com")))
        self.assertIsNone(extract_code(self.mail(subject="다른 메일")))
        self.assertIsNone(extract_code(self.mail(text="인증 코드 123456 다른 번호 654321")))
        self.assertIsNone(extract_code(self.mail(text="1234567")))

    def test_old_uid_is_not_fetched_even_when_search_returns_it(self):
        reader = NaverEmailReader()
        reader.baseline = (5, 100)
        client = MagicMock()
        client.response.return_value = ("UIDVALIDITY", [b"5"])
        client.uid.return_value = ("OK", [b"99"])
        connection = MagicMock()
        connection.__enter__.return_value = client
        with patch.object(reader, "connect", return_value=connection):
            self.assertIsNone(reader.find_code())
        self.assertEqual(client.uid.call_count, 1)

    def test_only_new_matching_mail_body_is_fetched_without_read_flag(self):
        reader = NaverEmailReader()
        reader.baseline = (5, 100)
        client = MagicMock()
        client.response.return_value = ("UIDVALIDITY", [b"5"])
        raw = self.mail()
        client.uid.side_effect = [("OK", [b"99 100"]),
                                  ("OK", [(b"header", raw)]), ("OK", [(b"body", raw)])]
        connection = MagicMock()
        connection.__enter__.return_value = client
        with patch.object(reader, "connect", return_value=connection):
            self.assertEqual(reader.find_code(), "074200")
        self.assertEqual(client.uid.call_args.args, ("fetch", b"100", "(BODY.PEEK[])"))

    def test_mailbox_reset_is_rejected(self):
        reader = NaverEmailReader()
        reader.baseline = (5, 100)
        client = MagicMock()
        client.response.return_value = ("UIDVALIDITY", [b"6"])
        connection = MagicMock()
        connection.__enter__.return_value = client
        with patch.object(reader, "connect", return_value=connection):
            with self.assertRaises(ValueError):
                reader.find_code()
        client.uid.assert_not_called()

    def test_connection_uses_tls_and_readonly_inbox(self):
        client = MagicMock()
        client.select.return_value = ("OK", [b"0"])
        with patch("utils.naver_email.imaplib.IMAP4_SSL", return_value=client) as connect, \
             patch("utils.naver_email.settings.wehago_mail_username", "test@naver.com"), \
             patch("utils.naver_email.settings.wehago_mail_app_password", SecretStr("dummy")):
            with NaverEmailReader().connect():
                pass
        self.assertEqual(connect.call_args.args, ("imap.naver.com", 993))
        client.select.assert_called_once_with("INBOX", readonly=True)
        client.logout.assert_called_once()


class MailFallbackTest(unittest.IsolatedAsyncioTestCase):
    async def test_automatic_success_does_not_request_telegram(self):
        auth = TelegramEmailAuth()
        auth.mailbox = MagicMock(wait_for_code=AsyncMock(return_value="012345"))
        auth.wait_for_telegram_code = AsyncMock()
        self.assertEqual(await auth.wait_for_code(), "012345")
        auth.wait_for_telegram_code.assert_not_awaited()

    async def test_mail_failure_switches_to_telegram(self):
        auth = TelegramEmailAuth()
        auth.mailbox = MagicMock(wait_for_code=AsyncMock(side_effect=TimeoutError()))
        auth.wait_for_telegram_code = AsyncMock(return_value="012345")
        with patch("utils.wehago_email_auth.settings.telegram_bot_token", "dummy"), \
             patch("utils.wehago_email_auth.settings.telegram_chat_id", "123"):
            self.assertEqual(await auth.wait_for_code(), "012345")
        auth.wait_for_telegram_code.assert_awaited_once()

    async def test_mail_connection_failure_leaves_manual_path_available(self):
        auth = TelegramEmailAuth()
        with patch("utils.wehago_email_auth.NaverEmailReader.configured", return_value=True), \
             patch("utils.wehago_email_auth.NaverEmailReader.prepare", side_effect=OSError("dummy")):
            await auth.prepare_mailbox()
        self.assertIsNone(auth.mailbox)


if __name__ == "__main__":
    unittest.main()
