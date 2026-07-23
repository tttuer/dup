from datetime import date, datetime
from typing import List, Optional

from pydantic import ConfigDict, Field

from domain.responses.base_response import BaseResponse


class PaymentTask(BaseResponse):
    """실제 납부를 추적하는 독립 업무."""

    id: str
    title: str
    request_name: str = ""
    category: str = ""
    requested_amount: Optional[int] = Field(default=None, ge=0)
    due_date: Optional[date] = None
    assignee_id: str
    assignee_name: str
    requester_id: str
    requester_name: str
    description: str = ""
    status: str = "PENDING_SETUP"
    is_request_confirmed: bool = False
    confirmed_at: Optional[datetime] = None
    confirmed_by: Optional[str] = None
    paid_amount: Optional[int] = Field(default=None, ge=0)
    paid_at: Optional[date] = None
    completed_at: Optional[datetime] = None
    completion_note: str = ""
    request_file_ids: List[str] = Field(default_factory=list)
    receipt_file_ids: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(extra="ignore")
