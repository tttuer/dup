from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class DocumentIntegrityResponse(BaseModel):
    id: str
    request_id: str
    content_hash: str
    previous_hash: Optional[str] = None
    hash_algorithm: str = "SHA-256"
    document_version: int = 1
    metadata_hash: str
    created_at: datetime
    created_by: str
    verification_count: int = 0
    last_verified_at: Optional[datetime] = None
    is_tampered: bool = False
    
    class Config:
        from_attributes = True


class DocumentIntegrityChainResponse(BaseModel):
    """문서 무결성 체인을 나타내는 응답 모델"""
    request_id: str
    chain: List[DocumentIntegrityResponse]
    is_valid: bool = True
    broken_at_version: Optional[int] = None
    
    class Config:
        from_attributes = True


class IntegrityVerificationResponse(BaseModel):
    """무결성 검증 결과 응답"""
    request_id: str
    is_valid: bool
    verified_at: datetime
    content_hash_valid: bool
    metadata_hash_valid: bool
    chain_valid: bool
    error_message: Optional[str] = None
    tampered_fields: List[str] = Field(default_factory=list)
    
    class Config:
        from_attributes = True