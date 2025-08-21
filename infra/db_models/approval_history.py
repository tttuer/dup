from datetime import datetime
from typing import Optional

from beanie import Document
from pydantic import Field

from common.auth import ApprovalAction


class ApprovalHistory(Document):
    id: str
    request_id: str
    approver_id: str
    action: ApprovalAction    # APPROVE, REJECT, CANCEL
    comment: Optional[str] = Field(default=None)
    created_at: datetime
    ip_address: Optional[str] = Field(default=None)

    class Settings:
        name = "approval_histories"