from datetime import date, datetime

from beanie import Document, Indexed
from pydantic import Field
from pymongo import ASCENDING, IndexModel

from domain.payment_recurrence import PaymentRecurrenceRule


class PaymentTaskSeries(Document):
    id: str
    name: str = ""
    category: str = ""
    requested_amount: int | None = Field(default=None, ge=0)
    description: str = ""
    assignee_id: Indexed(str)
    assignee_name: str
    requester_id: Indexed(str)
    requester_name: str
    start_date: date
    recurrence: PaymentRecurrenceRule
    generated_count: int = 0
    next_due_date: date | None = None
    status: str = "ACTIVE"
    request_file_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Settings:
        name = "payment_task_series"
        indexes = [
            IndexModel([("status", ASCENDING), ("next_due_date", ASCENDING)]),
            IndexModel([("requester_id", ASCENDING), ("status", ASCENDING)]),
        ]
