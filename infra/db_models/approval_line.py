from datetime import datetime
from typing import Optional

from beanie import Document, Indexed
from pydantic import Field
from pymongo import IndexModel, ASCENDING

from common.auth import ApprovalStatus


class ApprovalLine(Document):
    id: str
    request_id: Indexed(str)           # 결재 요청 ID - 인덱스 추가
    approver_id: Indexed(str)          # 결재자 ID - 인덱스 추가
    approver_name: str        # 결재자 이름
    step_order: int           # 결재 순서
    is_required: bool = Field(default=True)         # 필수 결재 여부
    is_parallel: bool = Field(default=False)         # 병렬 결재 여부
    status: ApprovalStatus = Field(default=ApprovalStatus.PENDING)    # 개별 결재 상태
    approved_at: Optional[datetime] = Field(default=None)
    comment: Optional[str] = Field(default=None)    # 결재 의견

    class Settings:
        name = "approval_lines"
        indexes = [
            # 복합 인덱스: 결재자별 상태 (가장 중요!)
            IndexModel([("approver_id", ASCENDING), ("status", ASCENDING)]),
            # 복합 인덱스: 요청별 단계 순서
            IndexModel([("request_id", ASCENDING), ("step_order", ASCENDING)]),
            # 복합 인덱스: 결재자별 상태와 승인일
            IndexModel([("approver_id", ASCENDING), ("status", ASCENDING), ("approved_at", ASCENDING)]),
            # 단일 인덱스: 상태별 조회
            IndexModel([("status", ASCENDING)]),
        ]