from datetime import datetime
from typing import Optional

from beanie import Document
from pydantic import Field
from pymongo import IndexModel, ASCENDING, DESCENDING


class DocumentIntegrity(Document):
    id: str
    request_id: str                 # 결재 요청 ID
    content_hash: str               # 문서 내용 해시 (SHA-256)
    previous_hash: Optional[str] = Field(default=None)  # 이전 해시 (체인 연결)
    hash_algorithm: str = Field(default="SHA-256")      # 해시 알고리즘
    document_version: int = Field(default=1)            # 문서 버전
    metadata_hash: str              # 메타데이터 해시 (결재선, 첨부파일 등)
    created_at: datetime            # 무결성 기록 생성 시간
    created_by: str                 # 무결성 기록 생성자
    verification_count: int = Field(default=0)  # 검증 횟수
    last_verified_at: Optional[datetime] = Field(default=None)  # 마지막 검증 시간
    is_tampered: bool = Field(default=False)    # 위변조 감지 여부
    
    class Settings:
        name = "document_integrity"
        indexes = [
            # request_id별 조회 (가장 중요)
            IndexModel([("request_id", ASCENDING)]),
            # 생성일 기준 조회 (최신순)
            IndexModel([("created_at", DESCENDING)]),
            # 위변조 감지된 문서 조회
            IndexModel([("is_tampered", ASCENDING)]),
            # 복합 인덱스: request_id + version (버전 관리용)
            IndexModel([("request_id", ASCENDING), ("document_version", ASCENDING)]),
        ]