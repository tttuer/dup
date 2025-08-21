from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class DefaultApprovalStep(BaseModel):
    step_order: int           # 결재 순서
    approver_id: str          # 기본 결재자 ID (또는 직책/부서)
    is_required: bool = True  # 필수 결재 여부
    is_parallel: bool = False # 병렬 결재 여부


class DocumentTemplate(BaseModel):
    id: str
    name: str                    # 양식명 (업무기안, 지출결의서 등)
    description: Optional[str] = None   # 양식 설명
    category: str               # 카테고리 (업무, 지출, 인사 등)
    document_prefix: Optional[str] = None        # 문서번호 프리픽스
    default_approval_steps: List[DefaultApprovalStep] = Field(default_factory=list)  # 기본 결재선
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(extra="ignore")