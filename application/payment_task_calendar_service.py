"""Google Calendar events and Telegram summaries for payment tasks."""

import asyncio
import hashlib
import json
from datetime import date, datetime, timedelta
from typing import Dict

import aiohttp
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pytz import timezone

from domain.payment_task import PaymentTask
from domain.repository.payment_task_repo import IPaymentTaskRepository
from utils.settings import settings


class PaymentTaskCalendarService:
    calendar_scope = "https://www.googleapis.com/auth/calendar"

    def __init__(self, payment_task_repo: IPaymentTaskRepository):
        self.payment_task_repo = payment_task_repo

    @property
    def calendar_enabled(self) -> bool:
        return bool(settings.google_calendar_id and settings.google_service_account_json)

    async def sync_task(self, task: PaymentTask) -> None:
        """Create or update one all-day event without blocking the API server."""
        if not self.calendar_enabled:
            return
        event_id = await asyncio.to_thread(self._sync_task, task)
        task.google_calendar_event_id = event_id
        task.calendar_sync_needed = False
        await self.payment_task_repo.update(task)

    async def retry_unsynced_tasks(self) -> None:
        if not self.calendar_enabled:
            return
        for task in await self.payment_task_repo.find_for_calendar_sync():
            try:
                await self.sync_task(task)
            except Exception as error:
                print(f"납부 업무 구글 캘린더 동기화 재시도 실패 ({task.id}): {error}")

    async def send_daily_summary(self) -> None:
        if not (settings.telegram_bot_token and settings.telegram_chat_id):
            return
        counts = await self.payment_task_repo.get_daily_summary(self._today())
        message = (
            "🔔 DUP 납부 요약\n\n"
            f"오늘 납부 {counts['today_count']}건\n"
            f"기한 초과 {counts['overdue_count']}건\n"
            f"기한 미설정 {counts['unset_count']}건\n\n"
            "노션 캘린더에서 구글 캘린더 일정을 확인해 주세요."
        )
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"chat_id": settings.telegram_chat_id, "text": message}) as response:
                await self._raise_for_error(response, "텔레그램 납부 요약 발송")

    def _sync_task(self, task: PaymentTask) -> str | None:
        service = self._calendar_service()
        event_id = task.google_calendar_event_id or self._event_id(task.id)
        if not task.due_date:
            self._delete_event(service, event_id)
            return None

        event = self._event(task)
        try:
            service.events().update(
                calendarId=settings.google_calendar_id, eventId=event_id, body=event
            ).execute()
        except HttpError as error:
            if error.resp.status != 404:
                raise
            service.events().insert(
                calendarId=settings.google_calendar_id, body={**event, "id": event_id}
            ).execute()
        return event_id

    def _calendar_service(self):
        try:
            info = json.loads(settings.google_service_account_json or "")
        except json.JSONDecodeError as error:
            raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON 형식이 올바르지 않습니다.") from error
        credentials = service_account.Credentials.from_service_account_info(info, scopes=[self.calendar_scope])
        return build("calendar", "v3", credentials=credentials, cache_discovery=False)

    def _delete_event(self, service, event_id: str) -> None:
        try:
            service.events().delete(calendarId=settings.google_calendar_id, eventId=event_id).execute()
        except HttpError as error:
            if error.resp.status != 404:
                raise

    @staticmethod
    def _event_id(task_id: str) -> str:
        return "dup" + hashlib.sha256(task_id.encode()).hexdigest()[:32]

    @staticmethod
    def _event(task: PaymentTask) -> Dict[str, object]:
        return {
            "summary": task.request_name or task.title,
            "description": f"DUP에서 확인\n{settings.frontend_base_url.rstrip('/')}/approval/payment-tasks/{task.id}",
            "start": {"date": task.due_date.isoformat()},
            "end": {"date": (task.due_date + timedelta(days=1)).isoformat()},
            "extendedProperties": {"private": {"dup_payment_task_id": task.id}},
        }

    @staticmethod
    def _today() -> date:
        return datetime.now(timezone("Asia/Seoul")).date()

    @staticmethod
    async def _raise_for_error(response: aiohttp.ClientResponse, action: str) -> None:
        if response.status < 400:
            return
        body = await response.text()
        raise RuntimeError(f"{action} 실패 ({response.status}): {body[:500]}")
