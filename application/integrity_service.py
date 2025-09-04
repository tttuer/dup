import hashlib
import json
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from dependency_injector.wiring import inject
from fastapi import HTTPException
from ulid import ULID

from application.base_service import BaseService
from domain.repository.document_integrity_repo import IDocumentIntegrityRepository
from domain.repository.approval_request_repo import IApprovalRequestRepository
from domain.repository.approval_line_repo import IApprovalLineRepository
from domain.repository.approval_history_repo import IApprovalHistoryRepository
from domain.repository.user_repo import IUserRepository
from domain.document_integrity import (
    DocumentIntegrityResponse, 
    DocumentIntegrityChainResponse,
    IntegrityVerificationResponse
)
from infra.db_models.document_integrity import DocumentIntegrity
from utils.time import get_utc_now_naive


class IntegrityService(BaseService):
    @inject
    def __init__(
        self,
        integrity_repo: IDocumentIntegrityRepository,
        approval_repo: IApprovalRequestRepository,
        line_repo: IApprovalLineRepository,
        history_repo: IApprovalHistoryRepository,
        user_repo: IUserRepository,
    ):
        super().__init__(user_repo)
        self.integrity_repo = integrity_repo
        self.approval_repo = approval_repo
        self.line_repo = line_repo
        self.history_repo = history_repo
        self.ulid = ULID()

    async def create_document_integrity(
        self,
        request_id: str,
        created_by: str,
    ) -> DocumentIntegrityResponse:
        """결재 완료 시 문서 무결성 기록 생성"""
        
        # 결재 요청서 조회
        request = await self.approval_repo.find_by_id(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Approval request not found")
        
        # 사용자 검증
        await self.validate_user_exists(created_by)
        
        # 문서 내용 해시 생성
        content_hash = await self._generate_content_hash(request)
        
        # 메타데이터 해시 생성 (결재선, 히스토리, 첨부파일)
        metadata_hash = await self._generate_metadata_hash(request_id)
        
        # 이전 무결성 기록과 체인 연결
        latest_integrity = await self.integrity_repo.find_latest_by_request_id(request_id)
        next_version = (latest_integrity.document_version + 1) if latest_integrity else 1
        previous_hash = latest_integrity.content_hash if latest_integrity else None
        
        # 무결성 기록 생성
        integrity = DocumentIntegrity(
            id=self.ulid.generate(),
            request_id=request_id,
            content_hash=content_hash,
            previous_hash=previous_hash,
            hash_algorithm="SHA-256",
            document_version=next_version,
            metadata_hash=metadata_hash,
            created_at=get_utc_now_naive(),
            created_by=created_by,
            verification_count=0,
            is_tampered=False,
        )
        
        saved_integrity = await self.integrity_repo.save(integrity)
        return DocumentIntegrityResponse.model_validate(saved_integrity.model_dump())

    async def verify_document_integrity(self, request_id: str, user_id: str) -> IntegrityVerificationResponse:
        """문서 무결성 검증"""
        
        # 권한 확인
        await self._validate_access_permission(request_id, user_id)
        
        # 최신 무결성 기록 조회
        latest_integrity = await self.integrity_repo.find_latest_by_request_id(request_id)
        if not latest_integrity:
            return IntegrityVerificationResponse(
                request_id=request_id,
                is_valid=False,
                verified_at=get_utc_now_naive(),
                content_hash_valid=False,
                metadata_hash_valid=False,
                chain_valid=False,
                error_message="No integrity record found",
                tampered_fields=[]
            )
        
        # 현재 문서 상태로 해시 재생성
        request = await self.approval_repo.find_by_id(request_id)
        current_content_hash = await self._generate_content_hash(request)
        current_metadata_hash = await self._generate_metadata_hash(request_id)
        
        # 해시 검증
        content_hash_valid = latest_integrity.content_hash == current_content_hash
        metadata_hash_valid = latest_integrity.metadata_hash == current_metadata_hash
        
        # 체인 검증
        chain_valid = await self._verify_integrity_chain(request_id)
        
        # 위변조된 필드 식별
        tampered_fields = []
        if not content_hash_valid:
            tampered_fields.append("content")
        if not metadata_hash_valid:
            tampered_fields.append("metadata")
        if not chain_valid:
            tampered_fields.append("chain")
        
        is_valid = content_hash_valid and metadata_hash_valid and chain_valid
        verified_at = get_utc_now_naive()
        
        # 검증 정보 업데이트
        await self.integrity_repo.update_verification_info(
            latest_integrity.id, 
            verified_at, 
            not is_valid
        )
        
        return IntegrityVerificationResponse(
            request_id=request_id,
            is_valid=is_valid,
            verified_at=verified_at,
            content_hash_valid=content_hash_valid,
            metadata_hash_valid=metadata_hash_valid,
            chain_valid=chain_valid,
            error_message=None if is_valid else "Document integrity compromised",
            tampered_fields=tampered_fields
        )

    async def get_integrity_chain(self, request_id: str, user_id: str) -> DocumentIntegrityChainResponse:
        """문서 무결성 체인 조회"""
        
        # 권한 확인
        await self._validate_access_permission(request_id, user_id)
        
        chain_records = await self.integrity_repo.get_chain_by_request_id(request_id)
        chain_responses = [
            DocumentIntegrityResponse.model_validate(record.model_dump()) 
            for record in chain_records
        ]
        
        # 체인 유효성 검증
        is_valid = await self._verify_integrity_chain(request_id)
        broken_at_version = None
        
        if not is_valid and len(chain_records) > 1:
            # 어느 버전에서 체인이 깨졌는지 찾기
            for i in range(1, len(chain_records)):
                current = chain_records[i]
                previous = chain_records[i-1]
                
                if current.previous_hash != previous.content_hash:
                    broken_at_version = current.document_version
                    break
        
        return DocumentIntegrityChainResponse(
            request_id=request_id,
            chain=chain_responses,
            is_valid=is_valid,
            broken_at_version=broken_at_version
        )

    async def get_tampered_documents(
        self, 
        user_id: str, 
        page: int = 1, 
        page_size: int = 20
    ) -> Tuple[List[DocumentIntegrityResponse], int]:
        """위변조된 문서 목록 조회 (관리자 전용)"""
        
        # 관리자 권한 확인
        user = await self.validate_user_exists(user_id)
        is_admin = any(role.value == "ADMIN" for role in user.roles)
        if not is_admin:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        tampered_records, total = await self.integrity_repo.find_tampered_documents(page, page_size)
        
        responses = [
            DocumentIntegrityResponse.model_validate(record.model_dump()) 
            for record in tampered_records
        ]
        
        return responses, total

    async def _generate_content_hash(self, request) -> str:
        """문서 내용 해시 생성"""
        content_data = {
            "id": request.id,
            "title": request.title,
            "content": request.content,
            "form_data": request.form_data,
            "template_id": request.template_id,
            "document_number": request.document_number,
            "requester_id": request.requester_id,
            "department_id": request.department_id,
            "status": request.status.value if hasattr(request.status, 'value') else str(request.status),
            "completed_at": request.completed_at.isoformat() if request.completed_at else None,
        }
        
        # JSON 정렬하여 일관된 해시 생성
        content_json = json.dumps(content_data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content_json.encode('utf-8')).hexdigest()

    async def _generate_metadata_hash(self, request_id: str) -> str:
        """메타데이터 해시 생성 (결재선, 히스토리)"""
        
        # 결재선 정보
        approval_lines = await self.line_repo.find_by_request_id(request_id)
        lines_data = [
            {
                "approver_id": line.approver_id,
                "approver_name": line.approver_name,
                "step_order": line.step_order,
                "status": line.status.value if hasattr(line.status, 'value') else str(line.status),
                "is_required": line.is_required,
                "is_parallel": line.is_parallel,
                "approved_at": line.approved_at.isoformat() if line.approved_at else None,
                "comment": line.comment,
            }
            for line in sorted(approval_lines, key=lambda x: x.step_order)
        ]
        
        # 결재 히스토리
        histories = await self.history_repo.find_by_request_id(request_id)
        history_data = [
            {
                "approver_id": history.approver_id,
                "approver_name": history.approver_name,
                "action": history.action.value if hasattr(history.action, 'value') else str(history.action),
                "created_at": history.created_at.isoformat(),
                "ip_address": history.ip_address,
                "comment": history.comment,
            }
            for history in sorted(histories, key=lambda x: x.created_at)
        ]
        
        metadata = {
            "approval_lines": lines_data,
            "histories": history_data,
            "lines_count": len(lines_data),
            "histories_count": len(history_data),
        }
        
        metadata_json = json.dumps(metadata, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(metadata_json.encode('utf-8')).hexdigest()

    async def _verify_integrity_chain(self, request_id: str) -> bool:
        """무결성 체인 검증"""
        
        chain_records = await self.integrity_repo.get_chain_by_request_id(request_id)
        
        if len(chain_records) <= 1:
            return True
        
        # 체인 연결 검증
        for i in range(1, len(chain_records)):
            current = chain_records[i]
            previous = chain_records[i-1]
            
            # 이전 해시가 올바르게 연결되어 있는지 확인
            if current.previous_hash != previous.content_hash:
                return False
            
            # 버전 순서가 올바른지 확인
            if current.document_version != previous.document_version + 1:
                return False
        
        return True

    async def _validate_access_permission(self, request_id: str, user_id: str) -> None:
        """접근 권한 검증 (기안자, 결재자, 관리자만)"""
        
        request = await self.approval_repo.find_by_id(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Approval request not found")
        
        user = await self.validate_user_exists(user_id)
        
        # 기안자인지 확인
        if request.requester_id == user_id:
            return
        
        # 결재자인지 확인
        approval_lines = await self.line_repo.find_by_request_id(request_id)
        is_approver = any(line.approver_id == user_id for line in approval_lines)
        if is_approver:
            return
        
        # 관리자인지 확인
        is_admin = any(role.value == "ADMIN" for role in user.roles)
        if is_admin:
            return
        
        raise HTTPException(status_code=403, detail="No permission to access this document integrity")