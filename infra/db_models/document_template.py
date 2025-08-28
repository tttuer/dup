from datetime import datetime
from typing import Optional, List

from beanie import Document
from pydantic import Field

from domain.document_template import DefaultApprovalStep


class DocumentTemplate(Document):
    id: str
    name: str                    # 양식명 (업무기안, 지출결의서 등)
    description: Optional[str] = Field(default=None)   # 양식 설명
    category: str               # 카테고리 (업무, 지출, 인사 등)
    document_prefix: Optional[str] = Field(default=None)        # 문서번호 프리픽스
    default_approval_steps: List[DefaultApprovalStep] = Field(default_factory=list)  # 기본 결재선
    is_active: bool = Field(default=True)
    created_at: datetime
    updated_at: datetime

    class Settings:
        name = "document_templates"