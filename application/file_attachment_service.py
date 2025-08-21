import os
from datetime import datetime
from typing import List, Optional
from dependency_injector.wiring import inject
from fastapi import HTTPException, UploadFile
from ulid import ULID

from application.base_service import BaseService
from domain.repository.attached_file_repo import IAttachedFileRepository
from domain.repository.approval_request_repo import IApprovalRequestRepository
from domain.repository.user_repo import IUserRepository
from domain.attached_file import AttachedFile
from common.auth import DocumentStatus


class FileAttachmentService(BaseService[AttachedFile]):
    @inject
    def __init__(
        self,
        file_repo: IAttachedFileRepository,
        approval_repo: IApprovalRequestRepository,
        user_repo: IUserRepository,
    ):
        super().__init__(user_repo)
        self.file_repo = file_repo
        self.approval_repo = approval_repo
        self.ulid = ULID()
        self.upload_dir = "uploads/approvals"  # 설정으로 분리 가능
        self.max_file_size = 20 * 1024 * 1024  # 20MB
        self.allowed_extensions = {
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.txt', '.jpg', '.jpeg', '.png', '.gif', '.zip', '.rar'
        }

    async def upload_file(
        self,
        request_id: str,
        file: UploadFile,
        uploaded_by: str,
        is_reference: bool = False,
    ) -> AttachedFile:
        # 요청서 확인 및 권한 검증
        request = await self.approval_repo.find_by_id(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Approval request not found")
        
        # 업로드 권한 확인 (기안자만 가능, 단 완료된 후에는 불가)
        if request.requester_id != uploaded_by:
            raise HTTPException(status_code=403, detail="Only requester can upload files")
        
        if request.status in [DocumentStatus.APPROVED, DocumentStatus.REJECTED, DocumentStatus.CANCELLED]:
            raise HTTPException(status_code=400, detail="Cannot upload files to completed requests")

        # 파일 검증
        await self._validate_file(file)

        # 파일 저장
        file_path = await self._save_file(file, request_id)

        # DB에 저장
        attached_file = AttachedFile(
            id=self.ulid.generate(),
            request_id=request_id,
            file_name=file.filename,
            file_path=file_path,
            file_size=file.size or 0,
            file_type=file.content_type or "",
            is_reference=is_reference,
            uploaded_at=datetime.now(),
            uploaded_by=uploaded_by,
        )

        await self.file_repo.save(attached_file)
        return attached_file

    async def get_files(self, request_id: str, user_id: str) -> List[AttachedFile]:
        # 권한 확인
        await self._validate_request_access(request_id, user_id)
        
        return await self.file_repo.find_by_request_id(request_id)

    async def delete_file(self, file_id: str, user_id: str) -> None:
        file = await self.file_repo.find_by_id(file_id)
        if not file:
            raise HTTPException(status_code=404, detail="File not found")

        # 요청서 확인
        request = await self.approval_repo.find_by_id(file.request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Approval request not found")

        # 권한 확인 (업로드한 사용자 또는 기안자만 삭제 가능)
        if file.uploaded_by != user_id and request.requester_id != user_id:
            raise HTTPException(status_code=403, detail="No permission to delete this file")
        
        if request.status in [DocumentStatus.APPROVED, DocumentStatus.REJECTED, DocumentStatus.CANCELLED]:
            raise HTTPException(status_code=400, detail="Cannot delete files from completed requests")

        # 실제 파일 삭제
        try:
            if os.path.exists(file.file_path):
                os.remove(file.file_path)
        except Exception as e:
            print(f"Failed to delete physical file: {e}")

        # DB에서 삭제
        await self.file_repo.delete(file_id)

    async def get_file_info(self, file_id: str, user_id: str) -> AttachedFile:
        file = await self.file_repo.find_by_id(file_id)
        if not file:
            raise HTTPException(status_code=404, detail="File not found")

        # 권한 확인
        await self._validate_request_access(file.request_id, user_id)
        
        return file

    async def _validate_file(self, file: UploadFile) -> None:
        # 파일 크기 확인
        if file.size and file.size > self.max_file_size:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds maximum limit of {self.max_file_size // (1024*1024)}MB"
            )

        # 파일 확장자 확인
        if file.filename:
            file_ext = os.path.splitext(file.filename)[1].lower()
            if file_ext not in self.allowed_extensions:
                raise HTTPException(
                    status_code=400,
                    detail=f"File type not allowed. Allowed types: {', '.join(self.allowed_extensions)}"
                )

    async def _save_file(self, file: UploadFile, request_id: str) -> str:
        # 업로드 디렉토리 생성
        request_dir = os.path.join(self.upload_dir, request_id)
        os.makedirs(request_dir, exist_ok=True)

        # 고유한 파일명 생성
        file_ext = os.path.splitext(file.filename)[1] if file.filename else ""
        unique_filename = f"{self.ulid.generate()}{file_ext}"
        file_path = os.path.join(request_dir, unique_filename)

        # 파일 저장
        try:
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

        return file_path

    async def _validate_request_access(self, request_id: str, user_id: str) -> None:
        request = await self.approval_repo.find_by_id(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Approval request not found")
        
        # 기안자인지 확인
        if request.requester_id == user_id:
            return
        
        # 결재자인지 확인
        from domain.repository.approval_line_repo import IApprovalLineRepository
        # 여기서는 간단히 처리하고, 실제로는 DI로 주입받아야 함
        
        # 관리자인지 확인
        user = await self.validate_user_exists(user_id)
        is_admin = any(role.value == "ADMIN" for role in user.roles)
        
        if not is_admin:
            raise HTTPException(status_code=403, detail="No permission to access this request")