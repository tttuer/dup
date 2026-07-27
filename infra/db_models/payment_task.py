from datetime import date, datetime
from typing import List, Optional

from beanie import Document, Indexed
from pydantic import Field
from pymongo import ASCENDING, DESCENDING, IndexModel


class PaymentTask(Document):
    """전자결재와 독립적으로 관리되는 납부 업무."""

    id: str
    title: str
    request_name: str = ""
    category: str = ""
    requested_amount: Optional[int] = Field(default=None, ge=0)
    due_date: Optional[date] = Field(default=None)
    assignee_id: Indexed(str)
    assignee_name: str
    requester_id: str
    requester_name: str
    description: str = ""
    status: str = "PENDING_SETUP"  # 기한 설정 필요 | 납부 대기 | 납부 완료
    is_request_confirmed: bool = False
    confirmed_at: Optional[datetime] = None
    confirmed_by: Optional[str] = None
    paid_amount: Optional[int] = Field(default=None, ge=0)
    paid_at: Optional[date] = None
    completed_at: Optional[datetime] = None
    completion_note: str = ""
    request_file_ids: List[str] = Field(default_factory=list)
    receipt_file_ids: List[str] = Field(default_factory=list)
    notion_sync_needed: bool = True
    created_at: datetime
    updated_at: datetime

    class Settings:
        name = "payment_tasks"
        indexes = [
            IndexModel([("assignee_id", ASCENDING), ("status", ASCENDING), ("due_date", ASCENDING)]),
            IndexModel([("assignee_id", ASCENDING), ("due_date", ASCENDING)]),
            IndexModel([("status", ASCENDING), ("due_date", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
        ]
