import io
import json
from datetime import datetime
from typing import Optional, Dict, Any
from dependency_injector.wiring import inject
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from ulid import ULID
import fitz  # PyMuPDF

from application.base_service import BaseService
from domain.repository.approval_request_repo import IApprovalRequestRepository
from domain.repository.approval_line_repo import IApprovalLineRepository
from domain.repository.approval_history_repo import IApprovalHistoryRepository
from domain.repository.user_repo import IUserRepository
from domain.repository.attached_file_repo import IAttachedFileRepository
from common.db import client
from utils.time import get_utc_now_naive


class LegalArchiveService(BaseService):
    @inject
    def __init__(
        self,
        approval_repo: IApprovalRequestRepository,
        line_repo: IApprovalLineRepository,
        history_repo: IApprovalHistoryRepository,
        user_repo: IUserRepository,
        file_repo: IAttachedFileRepository,
    ):
        super().__init__(user_repo)
        self.approval_repo = approval_repo
        self.line_repo = line_repo
        self.history_repo = history_repo
        self.file_repo = file_repo
        self.ulid = ULID()
        
        # GridFS 설정 (법적 문서 보관용)
        self.db = client.dup
        self.legal_fs = AsyncIOMotorGridFSBucket(self.db, bucket_name="legal_documents")

    async def create_legal_document(self, request_id: str, created_by: str) -> str:
        """결재 완료된 문서를 법적 효력이 있는 PDF로 변환 및 보관"""
        
        # 결재 요청서 조회
        request = await self.approval_repo.find_by_id(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Approval request not found")
        
        # 완료된 결재만 처리
        from common.auth import DocumentStatus
        if request.status != DocumentStatus.APPROVED:
            raise HTTPException(status_code=400, detail="Only approved documents can be archived")
        
        # 사용자 검증
        await self.validate_user_exists(created_by)
        
        try:
            # PDF 문서 생성
            pdf_content = await self._generate_pdf_document(request_id)
            
            # 메타데이터 준비
            metadata = await self._prepare_document_metadata(request_id)
            
            # GridFS에 저장 (읽기 전용)
            file_id = await self.legal_fs.upload_from_stream(
                filename=f"legal_{request.document_number}_{request_id}.pdf",
                source=io.BytesIO(pdf_content),
                metadata={
                    **metadata,
                    "created_by": created_by,
                    "created_at": get_utc_now_naive(),
                    "is_legal_document": True,
                    "readonly": True,
                }
            )
            
            return str(file_id)
            
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to create legal document: {str(e)}"
            )

    async def get_legal_document(self, request_id: str, user_id: str) -> tuple[bytes, str]:
        """법적 문서 다운로드"""
        
        # 권한 확인
        await self._validate_access_permission(request_id, user_id)
        
        # 문서 조회
        request = await self.approval_repo.find_by_id(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Approval request not found")
        
        # GridFS에서 파일 조회
        filename_pattern = f"legal_{request.document_number}_{request_id}.pdf"
        
        try:
            # 파일 스트림 조회
            file_cursor = self.legal_fs.find({"filename": filename_pattern})
            file_doc = await file_cursor.to_list(length=1)
            
            if not file_doc:
                raise HTTPException(status_code=404, detail="Legal document not found")
            
            file_id = file_doc[0]._id
            
            # 파일 내용 다운로드
            file_stream = await self.legal_fs.open_download_stream(file_id)
            content = await file_stream.read()
            
            return content, filename_pattern
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve legal document: {str(e)}"
            )

    async def verify_legal_document_exists(self, request_id: str) -> bool:
        """법적 문서 존재 여부 확인"""
        
        request = await self.approval_repo.find_by_id(request_id)
        if not request:
            return False
        
        filename_pattern = f"legal_{request.document_number}_{request_id}.pdf"
        
        try:
            file_cursor = self.legal_fs.find({"filename": filename_pattern})
            files = await file_cursor.to_list(length=1)
            return len(files) > 0
        except:
            return False

    async def _generate_pdf_document(self, request_id: str) -> bytes:
        """결재 문서를 PDF로 변환"""
        
        # 결재 정보 수집
        request = await self.approval_repo.find_by_id(request_id)
        approval_lines = await self.line_repo.find_by_request_id(request_id)
        histories = await self.history_repo.find_by_request_id(request_id)
        attached_files = await self.file_repo.find_by_request_id(request_id)
        
        # PDF 문서 생성
        doc = fitz.open()  # 새 PDF 문서
        
        try:
            # 첫 번째 페이지 생성
            page = doc.new_page()
            
            # 텍스트 삽입 위치
            y_pos = 72  # 1인치 여백
            line_height = 20
            
            def add_text(text: str, font_size: int = 12, bold: bool = False):
                nonlocal y_pos
                font_flags = fitz.TEXT_FONT_BOLD if bold else 0
                page.insert_text(
                    (72, y_pos), 
                    text, 
                    fontsize=font_size, 
                    flags=font_flags
                )
                y_pos += line_height
            
            # 문서 헤더
            add_text("전자결재 법적문서", 16, True)
            add_text("=" * 50, 12)
            y_pos += 10
            
            # 기본 정보
            add_text(f"문서번호: {request.document_number}", 12, True)
            add_text(f"제목: {request.title}")
            add_text(f"기안자: {request.requester_name}")
            add_text(f"기안일: {request.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
            add_text(f"완료일: {request.completed_at.strftime('%Y-%m-%d %H:%M:%S') if request.completed_at else 'N/A'}")
            add_text(f"상태: {request.status.value if hasattr(request.status, 'value') else str(request.status)}")
            y_pos += 20
            
            # 문서 내용
            add_text("문서 내용:", 14, True)
            add_text("-" * 40)
            
            # HTML 내용을 단순 텍스트로 변환 (간단한 처리)
            content_text = self._html_to_plain_text(request.content)
            for line in content_text.split('\n'):
                if y_pos > 700:  # 페이지 끝에 가까우면 새 페이지
                    page = doc.new_page()
                    y_pos = 72
                add_text(line[:80])  # 긴 줄 자르기
            
            y_pos += 20
            
            # 결재선 정보
            add_text("결재선 정보:", 14, True)
            add_text("-" * 40)
            
            sorted_lines = sorted(approval_lines, key=lambda x: x.step_order)
            for line in sorted_lines:
                status_text = line.status.value if hasattr(line.status, 'value') else str(line.status)
                approved_text = line.approved_at.strftime('%Y-%m-%d %H:%M:%S') if line.approved_at else 'N/A'
                
                if y_pos > 700:
                    page = doc.new_page()
                    y_pos = 72
                
                add_text(f"{line.step_order}단계: {line.approver_name} ({status_text})")
                add_text(f"  승인일시: {approved_text}")
                if line.comment:
                    add_text(f"  의견: {line.comment}")
                y_pos += 5
            
            y_pos += 20
            
            # 결재 히스토리
            add_text("결재 이력:", 14, True)
            add_text("-" * 40)
            
            sorted_histories = sorted(histories, key=lambda x: x.created_at)
            for history in sorted_histories:
                if y_pos > 700:
                    page = doc.new_page()
                    y_pos = 72
                
                action_text = history.action.value if hasattr(history.action, 'value') else str(history.action)
                add_text(f"{history.created_at.strftime('%Y-%m-%d %H:%M:%S')} - {history.approver_name}")
                add_text(f"  행위: {action_text}")
                add_text(f"  IP: {history.ip_address or 'N/A'}")
                if history.comment:
                    add_text(f"  의견: {history.comment}")
                y_pos += 5
            
            # 첨부파일 정보
            if attached_files:
                y_pos += 20
                add_text("첨부파일 목록:", 14, True)
                add_text("-" * 40)
                
                for file in attached_files:
                    if y_pos > 700:
                        page = doc.new_page()
                        y_pos = 72
                    
                    add_text(f"파일명: {file.file_name}")
                    add_text(f"크기: {file.file_size} bytes")
                    add_text(f"업로드일: {file.uploaded_at.strftime('%Y-%m-%d %H:%M:%S')}")
                    y_pos += 5
            
            # 문서 끝에 법적 효력 안내
            if y_pos > 650:
                page = doc.new_page()
                y_pos = 72
            
            y_pos += 30
            add_text("법적 효력 안내:", 14, True)
            add_text("=" * 50)
            add_text("본 문서는 전자문서법에 따라 법적 효력을 갖는 전자결재 문서입니다.")
            add_text("문서의 위변조 여부는 시스템의 무결성 검증 기능을 통해 확인할 수 있습니다.")
            add_text(f"문서 생성일시: {get_utc_now_naive().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # PDF 바이트 반환
            pdf_bytes = doc.tobytes()
            return pdf_bytes
            
        finally:
            doc.close()

    def _html_to_plain_text(self, html_content: str) -> str:
        """HTML을 일반 텍스트로 변환 (간단한 처리)"""
        import re
        
        # HTML 태그 제거
        text = re.sub(r'<[^>]+>', '', html_content)
        
        # HTML 엔티티 변환
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&amp;', '&')
        
        # 연속된 공백 정리
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()

    async def _prepare_document_metadata(self, request_id: str) -> Dict[str, Any]:
        """문서 메타데이터 준비"""
        
        request = await self.approval_repo.find_by_id(request_id)
        approval_lines = await self.line_repo.find_by_request_id(request_id)
        histories = await self.history_repo.find_by_request_id(request_id)
        
        return {
            "request_id": request_id,
            "document_number": request.document_number,
            "title": request.title,
            "requester_id": request.requester_id,
            "requester_name": request.requester_name,
            "status": request.status.value if hasattr(request.status, 'value') else str(request.status),
            "created_at": request.created_at,
            "completed_at": request.completed_at,
            "approval_lines_count": len(approval_lines),
            "histories_count": len(histories),
            "archived_at": get_utc_now_naive(),
        }

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
        
        raise HTTPException(status_code=403, detail="No permission to access this legal document")