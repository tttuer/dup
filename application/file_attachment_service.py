from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dependency_injector.wiring import inject
from fastapi import HTTPException, UploadFile, Response
from fastapi.responses import StreamingResponse
from ulid import ULID
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from bson import ObjectId
import io
import zipfile
from urllib.parse import quote

from application.base_service import BaseService
from domain.repository.attached_file_repo import IAttachedFileRepository
from domain.repository.approval_request_repo import IApprovalRequestRepository
from common.exceptions import InternalServerError
from domain.repository.approval_line_repo import IApprovalLineRepository
from domain.repository.user_repo import IUserRepository
from domain.attached_file import AttachedFile
from common.auth import DocumentStatus
from common.db import client
from utils.time import get_utc_now_naive


class FileAttachmentService(BaseService[AttachedFile]):
    @inject
    def __init__(
        self,
        file_repo: IAttachedFileRepository,
        approval_repo: IApprovalRequestRepository,
        line_repo: IApprovalLineRepository,
        user_repo: IUserRepository,
    ):
        super().__init__(user_repo)
        self.file_repo = file_repo
        self.approval_repo = approval_repo
        self.line_repo = line_repo
        self.ulid = ULID()
        self.max_file_size = 20 * 1024 * 1024  # 20MB
        # GridFS 설정
        self.db = client.dup
        self.fs = AsyncIOMotorGridFSBucket(self.db)
        self.allowed_extensions = {
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.xlsb', '.ppt', '.pptx',
            '.txt', '.jpg', '.jpeg', '.png', '.gif', '.zip', '.rar',
            '.hwp', '.hwpx'
        }

    async def upload_file(
        self,
        request_id: str,
        file: UploadFile,
        uploaded_by: str,
        is_reference: bool = False,
        attachment_type: str = "REQUEST",
    ) -> AttachedFile:
        # 요청서 확인 및 권한 검증
        request = await self.approval_repo.find_by_id(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Approval request not found")
        
        # 업로드 권한 확인 (기안자 또는 결재자)
        if request.requester_id != uploaded_by:
            approval_lines = await self.line_repo.find_by_request_id(request_id)
            is_approver = any(line.approver_id == uploaded_by for line in approval_lines)
            if not is_approver:
                raise HTTPException(status_code=403, detail="Only requester or approver can upload files")
        
        if request.status in [DocumentStatus.APPROVED, DocumentStatus.REJECTED, DocumentStatus.CANCELLED]:
            raise HTTPException(status_code=400, detail="Cannot upload files to completed requests")

        # 파일 검증
        await self._validate_file(file)

        # GridFS에 파일 저장
        gridfs_file_id = await self._save_file_to_gridfs(file, request_id)

        # DB에 저장
        attached_file = AttachedFile(
            id=self.ulid.generate(),
            request_id=request_id,
            file_name=file.filename,
            gridfs_file_id=str(gridfs_file_id),
            file_size=file.size or 0,
            file_type=file.content_type or "",
            is_reference=is_reference,
            attachment_type=attachment_type,
            uploaded_at=get_utc_now_naive(),
            uploaded_by=uploaded_by,
        )

        await self.file_repo.save(attached_file)
        return attached_file

    async def upload_payment_evidence(
        self,
        request_id: str,
        file: UploadFile,
        uploaded_by: str,
    ) -> AttachedFile:
        """승인 완료 뒤에도 납부 업무의 증빙만 제한적으로 추가한다.

        일반 첨부와 달리 완료된 문서의 원문을 수정하지 않고, 파일 종류를 명시해
        후속 처리 증빙으로 분리한다. 호출자는 PaymentTaskService가 담당자 권한을
        확인한 뒤에만 이 메서드를 사용할 수 있다.
        """
        request = await self.approval_repo.find_by_id(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Approval request not found")
        if request.status != DocumentStatus.APPROVED:
            raise HTTPException(status_code=400, detail="Payment evidence requires an approved request")

        await self._validate_file(file)
        gridfs_file_id = await self._save_file_to_gridfs(file, request_id)
        attached_file = AttachedFile(
            id=self.ulid.generate(),
            request_id=request_id,
            file_name=file.filename,
            gridfs_file_id=str(gridfs_file_id),
            file_size=file.size or 0,
            file_type=file.content_type or "",
            attachment_type="PAYMENT_EVIDENCE",
            uploaded_at=get_utc_now_naive(),
            uploaded_by=uploaded_by,
        )
        await self.file_repo.save(attached_file)
        return attached_file

    async def upload_payment_task_file(
        self,
        payment_task_id: str,
        file: UploadFile,
        uploaded_by: str,
        attachment_type: str = "PAYMENT_REQUEST",
    ) -> AttachedFile:
        """결재 문서 없이 생성된 납부 요청의 근거 파일을 저장한다."""
        await self._validate_file(file)
        gridfs_file_id = await self._save_file_to_gridfs(file, f"payment_task:{payment_task_id}")
        attached_file = AttachedFile(
            id=self.ulid.generate(),
            payment_task_id=payment_task_id,
            file_name=file.filename,
            gridfs_file_id=str(gridfs_file_id),
            file_size=file.size or 0,
            file_type=file.content_type or "",
            attachment_type=attachment_type,
            uploaded_at=get_utc_now_naive(),
            uploaded_by=uploaded_by,
        )
        await self.file_repo.save(attached_file)
        return attached_file

    async def get_payment_task_files(self, payment_task_id: str) -> List[Dict[str, Any]]:
        files = await self.file_repo.find_by_payment_task_id(payment_task_id)
        return [file.model_dump() for file in files]

    async def get_payment_task_file_stream(self, payment_task_id: str, file_id: str):
        file = await self.file_repo.find_by_id(file_id)
        if not file or file.payment_task_id != payment_task_id:
            raise HTTPException(status_code=404, detail="Payment task file not found")
        return await self._build_file_stream_response(file)

    async def delete_payment_task_file(self, payment_task_id: str, file_id: str) -> None:
        file = await self.file_repo.find_by_id(file_id)
        if not file or file.payment_task_id != payment_task_id:
            raise HTTPException(status_code=404, detail="Payment task file not found")
        try:
            await self.fs.delete(ObjectId(file.gridfs_file_id))
        except Exception as error:
            print(f"GridFS payment task file delete warning: {error}")
        await file.delete()

    async def get_files(self, request_id: str, user_id: str) -> List[AttachedFile]:
        # 권한 확인
        await self._validate_request_access(request_id, user_id)
        
        files = await self.file_repo.find_by_request_id(request_id)
        
        return files

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

        # GridFS에서 파일 삭제
        try:
            await self.fs.delete(ObjectId(file.gridfs_file_id))
        except Exception as e:
            print(f"GridFS 파일 삭제 경고 (무시됨): {e}")

        # DB에서 삭제
        await self.file_repo.delete_by_id(file_id)

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
            file_ext = "." + file.filename.split(".")[-1].lower() if "." in file.filename else ""
            if file_ext not in self.allowed_extensions:
                raise HTTPException(
                    status_code=400,
                    detail=f"File type not allowed. Allowed types: {', '.join(self.allowed_extensions)}"
                )
    
    async def get_file_stream(self, file_id: str, user_id: str):
        """GridFS에서 파일을 스트리밍으로 반환"""
        file = await self.file_repo.find_by_id(file_id)
        if not file:
            raise HTTPException(status_code=404, detail="File not found")
            
        # 권한 확인
        await self._validate_request_access(file.request_id, user_id)
        
        return await self._build_file_stream_response(file)

    async def _build_file_stream_response(self, file: AttachedFile):
        try:
            grid_out = await self.fs.open_download_stream(ObjectId(file.gridfs_file_id))
            content = await grid_out.read()
            encoded_filename = quote(file.file_name.encode('utf-8'))
            return Response(
                content=content,
                media_type=file.file_type,
                headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"},
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve file: {str(e)}")

    async def download_all_files_as_zip(self, request_id: str, user_id: str):
        """결재 요청의 모든 파일을 ZIP으로 일괄 다운로드"""
        # 권한 확인
        await self._validate_request_access(request_id, user_id)
        
        # 파일 목록 조회
        files = await self.file_repo.find_by_request_id(request_id)
        if not files:
            raise HTTPException(status_code=404, detail="No files found for this request")
        
        try:
            # ZIP 파일을 메모리에서 생성
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for file in files:
                    try:
                        # GridFS에서 파일 내용 가져오기
                        grid_out = await self.fs.open_download_stream(ObjectId(file.gridfs_file_id))
                        content = await grid_out.read()
                        
                        # ZIP에 파일 추가
                        zip_file.writestr(file.file_name, content)
                    except Exception as e:
                        continue
            
            zip_buffer.seek(0)
            
            # 파일명을 UTF-8로 인코딩
            zip_filename = f"approval_{request_id}_files.zip"
            encoded_filename = quote(zip_filename.encode('utf-8'))
            
            def generate_zip():
                yield zip_buffer.read()
            
            return StreamingResponse(
                generate_zip(),
                media_type="application/zip",
                headers={
                    "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
                }
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create ZIP file: {str(e)}")

    async def _save_file_to_gridfs(self, file: UploadFile, request_id: str) -> ObjectId:
        try:
            # 파일 내용 읽기
            content = await file.read()
            
            # GridFS에 저장
            file_id = await self.fs.upload_from_stream(
                filename=file.filename or "unknown",
                source=io.BytesIO(content),
                metadata={
                    "request_id": request_id,
                    "content_type": file.content_type or "",
                    "uploaded_at": get_utc_now_naive()
                }
            )
            
            return file_id
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save file to GridFS: {str(e)}")

    async def _validate_request_access(self, request_id: str, user_id: str) -> None:
        request = await self.approval_repo.find_by_id(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Approval request not found")
        
        # 기안자인지 확인
        if request.requester_id == user_id:
            return
        
        # 결재자인지 확인
        approval_lines = await self.line_repo.find_by_request_id(request_id)
        is_approver = any(line.approver_id == user_id for line in approval_lines)
        
        if is_approver:
            return
        
        # 관리자인지 확인
        user = await self.validate_user_exists(user_id)
        is_admin = any(role.value == "ADMIN" for role in user.roles)
        
        if not is_admin:
            raise HTTPException(status_code=403, detail="No permission to access this request")
