from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime

from infra.db_models.document_integrity import DocumentIntegrity


class IDocumentIntegrityRepository(ABC):
    
    @abstractmethod
    async def save(self, integrity: DocumentIntegrity) -> DocumentIntegrity:
        """무결성 기록 저장"""
        pass
    
    @abstractmethod
    async def find_by_id(self, integrity_id: str) -> Optional[DocumentIntegrity]:
        """ID로 무결성 기록 조회"""
        pass
    
    @abstractmethod
    async def find_by_request_id(self, request_id: str) -> List[DocumentIntegrity]:
        """결재 요청 ID로 모든 무결성 기록 조회"""
        pass
    
    @abstractmethod
    async def find_latest_by_request_id(self, request_id: str) -> Optional[DocumentIntegrity]:
        """결재 요청 ID로 최신 무결성 기록 조회"""
        pass
    
    @abstractmethod
    async def find_by_version(self, request_id: str, version: int) -> Optional[DocumentIntegrity]:
        """특정 버전의 무결성 기록 조회"""
        pass
    
    @abstractmethod
    async def find_tampered_documents(self, page: int = 1, page_size: int = 20) -> tuple[List[DocumentIntegrity], int]:
        """위변조된 문서 목록 조회 (페이징 포함)"""
        pass
    
    @abstractmethod
    async def update_verification_info(self, integrity_id: str, verified_at: datetime, is_tampered: bool) -> None:
        """검증 정보 업데이트"""
        pass
    
    @abstractmethod
    async def get_chain_by_request_id(self, request_id: str) -> List[DocumentIntegrity]:
        """결재 요청의 무결성 체인 조회 (버전 순서대로)"""
        pass