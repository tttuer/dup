from datetime import date
from typing import List, Optional

from domain.payment_task import PaymentTask as PaymentTaskVo
from domain.repository.payment_task_repo import IPaymentTaskRepository
from infra.db_models.payment_task import PaymentTask
from infra.repository.base_repo import BaseRepository


class PaymentTaskRepository(BaseRepository[PaymentTask], IPaymentTaskRepository):
    def __init__(self):
        super().__init__(PaymentTask)

    async def save(self, task: PaymentTaskVo) -> PaymentTask:
        document = PaymentTask(**task.model_dump())
        return await document.insert()

    async def find_by_assignee(
        self, assignee_id: str, status: Optional[str] = None, limit: int = 100
    ) -> List[PaymentTask]:
        filters = [PaymentTask.assignee_id == assignee_id]
        if status:
            filters.append(PaymentTask.status == status)
        return await PaymentTask.find(*filters).sort(PaymentTask.due_date).limit(limit).to_list()

    async def find_for_user(
        self, user_id: str, status: Optional[str] = None, limit: int = 100
    ) -> List[PaymentTask]:
        query = {"$or": [{"assignee_id": user_id}, {"requester_id": user_id}]}
        if status:
            query["status"] = status
        return await PaymentTask.find(query).sort(PaymentTask.due_date).limit(limit).to_list()

    async def get_assignee_summary(self, assignee_id: str) -> dict:
        active_query = {"assignee_id": assignee_id, "status": {"$ne": "COMPLETED"}}
        today_count = await PaymentTask.find({**active_query, "due_date": date.today()}).count()
        confirmation_count = await PaymentTask.find(
            {**active_query, "is_request_confirmed": False}
        ).count()
        return {"today_count": today_count, "confirmation_count": confirmation_count}

    async def find_for_notion_sync(self) -> List[PaymentTask]:
        query = {
            "$or": [
                {"notion_sync_needed": True},
                {"notion_sync_needed": {"$exists": False}, "status": {"$ne": "COMPLETED"}},
            ]
        }
        return await PaymentTask.find(query).sort(PaymentTask.updated_at).to_list()

    async def get_daily_summary(self, today: date) -> dict:
        active_query = {"status": {"$ne": "COMPLETED"}}
        today_count = await PaymentTask.find({**active_query, "due_date": today}).count()
        overdue_count = await PaymentTask.find({**active_query, "due_date": {"$lt": today}}).count()
        unset_count = await PaymentTask.find({**active_query, "due_date": None}).count()
        return {
            "today_count": today_count,
            "overdue_count": overdue_count,
            "unset_count": unset_count,
        }

    async def find_active_for_notion_status(self) -> List[PaymentTask]:
        return await PaymentTask.find({"status": {"$ne": "COMPLETED"}}).to_list()
