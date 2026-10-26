from datetime import date, datetime

from pydantic import ConfigDict, Field

from domain.payment_recurrence import PaymentRecurrenceRule
from domain.responses.base_response import BaseResponse


class PaymentTaskSeries(BaseResponse):
    id: str
    name: str = ""
    category: str = ""
    requested_amount: int | None = Field(default=None, ge=0)
    description: str = ""
    assignee_id: str
    assignee_name: str
    requester_id: str
    requester_name: str
    start_date: date
    recurrence: PaymentRecurrenceRule
    generated_count: int = 0
    next_due_date: date | None = None
    status: str = "ACTIVE"
    request_file_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(extra="ignore")
