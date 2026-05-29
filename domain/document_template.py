from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Any
from datetime import datetime
from domain.responses.base_response import BaseResponse


class SelectOption(BaseModel):
    label: str
    value: str


class FormField(BaseModel):
    name: str
    label: str
    type: str # text, number, date, select
    required: bool = False
    placeholder: Optional[str] = None
    options: Optional[List[SelectOption]] = None
    default_value: Optional[str] = None


class DefaultApprovalStep(BaseModel):
    step_order: int           # 결재 순서
    approver_id: str          # 기본 결재자 ID (또는 직책/부서)
    approver_user_id: Optional[str] = None # 실제 유저 ID
    approver_name: Optional[str] = None
    approver_department: Optional[str] = None
    approver_position: Optional[str] = None
    is_required: bool = True  # 필수 결재 여부
    is_parallel: bool = False # 병렬 결재 여부


class DocumentTemplate(BaseResponse):
    id: str
    name: str                    # 양식명 (업무기안, 지출결의서 등)
    description: Optional[str] = None   # 양식 설명
    category: str               # 카테고리 (업무, 지출, 인사 등)
    document_prefix: Optional[str] = None        # 문서번호 프리픽스
    content_template: Optional[str] = None
    default_approval_steps: List[DefaultApprovalStep] = Field(default_factory=list)  # 기본 결재선
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(extra="ignore")