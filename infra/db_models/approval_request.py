from datetime import datetime
from typing import Optional, Dict, Any

from beanie import Document, Indexed
from pydantic import Field
from pymongo import IndexModel, ASCENDING, DESCENDING

from common.auth import DocumentStatus


class ApprovalRequest(Document):
    id: str
    template_id: str           # 사용한 양식 ID
    document_number: str       # 자동 생성 문서번호d
    title: str                # 결재 제목
    content: str              # 결재 내용 (HTML)
    form_data: Dict[str, Any] = Field(default_factory=dict) # 양식별 추가 데이터
    requester_id: Indexed(str)         # 기안자 ID - 인덱스 추가
    requester_name: str       # 기안자 이름
    department_id: Optional[str] = Field(default=None)        # 기안 부서
    status: DocumentStatus    # 결재 상태
    current_step: int = Field(default=0)         # 현재 결재 단계
    created_at: Indexed(datetime, index_type=DESCENDING)  # 생성일 내림차순 인덱스
    updated_at: datetime
    submitted_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)

    class Settings:
        name = "approval_requests"
        indexes = [
            # 복합 인덱스: 기안자별 상태와 생성일 (가장 중요!)
            IndexModel([("requester_id", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)]),
            # 복합 인덱스: 상태별 생성일
            IndexModel([("status", ASCENDING), ("created_at", DESCENDING)]),
            # 템플릿별 생성일 인덱스
            IndexModel([("template_id", ASCENDING), ("created_at", DESCENDING)]),
            # 단일 인덱스: 상태별 조회
            IndexModel([("status", ASCENDING)]),
        ]