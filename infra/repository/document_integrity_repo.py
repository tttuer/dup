from typing import List, Optional
from datetime import datetime
from beanie.operators import Eq

from domain.repository.document_integrity_repo import IDocumentIntegrityRepository
from infra.db_models.document_integrity import DocumentIntegrity


class DocumentIntegrityRepository(IDocumentIntegrityRepository):
    
    async def save(self, integrity: DocumentIntegrity) -> DocumentIntegrity:
        """무결성 기록 저장"""
        await integrity.save()
        return integrity
    
    async def find_by_id(self, integrity_id: str) -> Optional[DocumentIntegrity]:
        """ID로 무결성 기록 조회"""
        return await DocumentIntegrity.find_one(Eq(DocumentIntegrity.id, integrity_id))
    
    async def find_by_request_id(self, request_id: str) -> List[DocumentIntegrity]:
        """결재 요청 ID로 모든 무결성 기록 조회"""
        return await DocumentIntegrity.find(
            Eq(DocumentIntegrity.request_id, request_id)
        ).sort(DocumentIntegrity.document_version.asc()).to_list()
    
    async def find_latest_by_request_id(self, request_id: str) -> Optional[DocumentIntegrity]:
        """결재 요청 ID로 최신 무결성 기록 조회"""
        return await DocumentIntegrity.find_one(
            Eq(DocumentIntegrity.request_id, request_id),
            sort=[("document_version", -1)]
        )
    
    async def find_by_version(self, request_id: str, version: int) -> Optional[DocumentIntegrity]:
        """특정 버전의 무결성 기록 조회"""
        return await DocumentIntegrity.find_one(
            Eq(DocumentIntegrity.request_id, request_id),
            Eq(DocumentIntegrity.document_version, version)
        )
    
    async def find_tampered_documents(self, page: int = 1, page_size: int = 20) -> tuple[List[DocumentIntegrity], int]:
        """위변조된 문서 목록 조회 (페이징 포함)"""
        query = DocumentIntegrity.find(
            Eq(DocumentIntegrity.is_tampered, True)
        ).sort(DocumentIntegrity.created_at.desc())
        
        # 총 개수 조회
        total = await query.count()
        
        # 페이징 적용
        skip = (page - 1) * page_size
        items = await query.skip(skip).limit(page_size).to_list()
        
        return items, total
    
    async def update_verification_info(self, integrity_id: str, verified_at: datetime, is_tampered: bool) -> None:
        """검증 정보 업데이트"""
        doc = await DocumentIntegrity.find_one(Eq(DocumentIntegrity.id, integrity_id))
        if doc:
            doc.verification_count += 1
            doc.last_verified_at = verified_at
            doc.is_tampered = is_tampered
            await doc.save()
    
    async def get_chain_by_request_id(self, request_id: str) -> List[DocumentIntegrity]:
        """결재 요청의 무결성 체인 조회 (버전 순서대로)"""
        return await DocumentIntegrity.find(
            Eq(DocumentIntegrity.request_id, request_id)
        ).sort(DocumentIntegrity.document_version.asc()).to_list()