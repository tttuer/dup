"""Notion calendar sync and Telegram summaries for payment tasks.

Only non-sensitive task data leaves DUP.  A missing integration setting makes
these methods harmless so local development and payment saving keep working.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

import aiohttp
from pytz import timezone

from domain.payment_task import PaymentTask
from domain.repository.payment_task_repo import IPaymentTaskRepository
from utils.settings import settings


class PaymentTaskNotificationService:
    notion_version = "2022-06-28"
    notion_base_url = "https://api.notion.com/v1"

    def __init__(self, payment_task_repo: IPaymentTaskRepository):
        self.payment_task_repo = payment_task_repo

    @property
    def notion_enabled(self) -> bool:
        return bool(settings.notion_api_token and settings.notion_payment_database_id)

    async def sync_task(self, task: PaymentTask) -> None:
        """Create or update one Notion page, keyed by DUP task ID."""
        if not self.notion_enabled:
            return

        headers = {
            "Authorization": f"Bearer {settings.notion_api_token}",
            "Notion-Version": self.notion_version,
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            page_id = await self._find_page_id(session, task.id)
            payload = {"properties": self._notion_properties(task)}
            if page_id:
                async with session.patch(f"{self.notion_base_url}/pages/{page_id}", json=payload) as response:
                    await self._raise_for_error(response, "노션 일정 수정")
            else:
                payload["parent"] = {"database_id": settings.notion_payment_database_id}
                async with session.post(f"{self.notion_base_url}/pages", json=payload) as response:
                    await self._raise_for_error(response, "노션 일정 생성")
        task.notion_sync_needed = False
        await self.payment_task_repo.update(task)

    async def retry_unsynced_tasks(self) -> None:
        """A retry is idempotent because sync_task always searches by DUP ID."""
        if not self.notion_enabled:
            return
        for task in await self.payment_task_repo.find_for_notion_sync():
            try:
                await self.sync_task(task)
            except Exception as error:
                # One failed page must not prevent the next payment task retry.
                print(f"납부 업무 노션 동기화 재시도 실패 ({task.id}): {error}")

    async def refresh_active_task_statuses(self) -> None:
        """At midnight, reflect newly overdue tasks in the Notion status."""
        if not self.notion_enabled:
            return
        for task in await self.payment_task_repo.find_active_for_notion_status():
            try:
                await self.sync_task(task)
            except Exception as error:
                task.notion_sync_needed = True
                await self.payment_task_repo.update(task)
                print(f"납부 업무 노션 상태 갱신 실패 ({task.id}): {error}")

    async def send_daily_summary(self) -> None:
        if not (settings.telegram_bot_token and settings.telegram_chat_id):
            return
        counts = await self.payment_task_repo.get_daily_summary(self._today())
        message = (
            "🔔 DUP 납부 요약\n\n"
            f"오늘 납부 {counts['today_count']}건\n"
            f"기한 초과 {counts['overdue_count']}건\n"
            f"기한 미설정 {counts['unset_count']}건\n\n"
            "노션 캘린더를 확인해 주세요."
        )
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"chat_id": settings.telegram_chat_id, "text": message}) as response:
                await self._raise_for_error(response, "텔레그램 납부 요약 발송")

    async def _find_page_id(self, session: aiohttp.ClientSession, task_id: str) -> Optional[str]:
        url = f"{self.notion_base_url}/databases/{settings.notion_payment_database_id}/query"
        payload = {"filter": {"property": "DUP 업무 ID", "rich_text": {"equals": task_id}}}
        async with session.post(url, json=payload) as response:
            data = await self._json_or_error(response, "노션 일정 조회")
        results = data.get("results", [])
        return results[0]["id"] if results else None

    def _notion_properties(self, task: PaymentTask) -> Dict[str, Any]:
        due_date = {"date": {"start": task.due_date.isoformat()}} if task.due_date else {"date": None}
        return {
            "업무명": {"title": [{"text": {"content": f"[납부] {task.request_name or task.title}"}}]},
            "납부일": due_date,
            "상태": {"select": {"name": self._status_name(task)}},
            "담당자": {"rich_text": [{"text": {"content": task.assignee_name}}]},
            "DUP에서 확인": {"url": f"{settings.frontend_base_url.rstrip('/')}/approval/payment-tasks/{task.id}"},
            "DUP 업무 ID": {"rich_text": [{"text": {"content": task.id}}]},
            "마지막 동기화": {"date": {"start": datetime.now(timezone('Asia/Seoul')).isoformat()}},
        }

    @staticmethod
    def _status_name(task: PaymentTask) -> str:
        if task.status == "COMPLETED":
            return "완료"
        if not task.due_date:
            return "기한 미설정"
        return "기한 초과" if task.due_date < PaymentTaskNotificationService._today() else "납부 대기"

    @staticmethod
    def _today() -> date:
        return datetime.now(timezone("Asia/Seoul")).date()

    @staticmethod
    async def _json_or_error(response: aiohttp.ClientResponse, action: str) -> Dict[str, Any]:
        if response.status < 400:
            return await response.json()
        body = await response.text()
        raise RuntimeError(f"{action} 실패 ({response.status}): {body[:500]}")

    @classmethod
    async def _raise_for_error(cls, response: aiohttp.ClientResponse, action: str) -> None:
        await cls._json_or_error(response, action)
