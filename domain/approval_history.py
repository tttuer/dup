from pydantic import ConfigDict
from typing import Optional
from datetime import datetime
from common.auth import ApprovalAction
from domain.responses.base_response import BaseResponse


class ApprovalHistory(BaseResponse):
    id: str
    request_id: str
    approver_id: str
    approver_name: str
    action: ApprovalAction    # APPROVE, REJECT, CANCEL
    comment: Optional[str] = None
    created_at: datetime
    ip_address: Optional[str] = None
    
    model_config = ConfigDict(extra="ignore")