from datetime import datetime
from typing import Optional, Dict, Any

from beanie import Document
from pydantic import Field

from common.auth import DocumentStatus


class ApprovalRequest(Document):
    id: str
    template_id: str           # 사용한 양식 ID
    document_number: str       # 자동 생성 문서번호d
    title: str                # 결재 제목
    content: str              # 결재 내용 (HTML)
    form_data: Dict[str, Any] = Field(default_factory=dict) # 양식별 추가 데이터
    requester_id: str         # 기안자 ID
    requester_name: str       # 기안자 이름
    department_id: Optional[str] = Field(default=None)        # 기안 부서
    status: DocumentStatus    # 결재 상태
    current_step: int = Field(default=0)         # 현재 결재 단계
    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)

    class Settings:
        name = "approval_requests"