from datetime import datetime
from typing import Optional

from beanie import Document
from pydantic import Field

from common.auth import ApprovalStatus


class ApprovalLine(Document):
    id: str
    request_id: str           # 결재 요청 ID
    approver_id: str          # 결재자 ID
    step_order: int           # 결재 순서
    is_required: bool = Field(default=True)         # 필수 결재 여부
    is_parallel: bool = Field(default=False)         # 병렬 결재 여부
    status: ApprovalStatus = Field(default=ApprovalStatus.PENDING)    # 개별 결재 상태
    approved_at: Optional[datetime] = Field(default=None)
    comment: Optional[str] = Field(default=None)    # 결재 의견

    class Settings:
        name = "approval_lines"