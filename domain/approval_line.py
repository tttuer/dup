from pydantic import ConfigDict
from typing import Optional
from datetime import datetime
from common.auth import ApprovalStatus
from domain.responses.base_response import BaseResponse


class ApprovalLine(BaseResponse):
    id: str
    request_id: str           # 결재 요청 ID
    approver_id: str          # 결재자 ID
    approver_name: str        # 결재자 이름
    step_order: int           # 결재 순서
    is_required: bool = True         # 필수 결재 여부
    is_parallel: bool = False         # 병렬 결재 여부
    status: ApprovalStatus = ApprovalStatus.PENDING    # 개별 결재 상태
    approved_at: Optional[datetime] = None
    comment: Optional[str] = None    # 결재 의견
    
    model_config = ConfigDict(extra="ignore")