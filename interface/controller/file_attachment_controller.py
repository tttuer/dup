from typing import List, Annotated
from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File
from fastapi.responses import FileResponse
import os

from application.file_attachment_service import FileAttachmentService
from common.auth import CurrentUser, get_current_user
from containers import Container
from domain.attached_file import AttachedFile

router = APIRouter(prefix="/files", tags=["file-attachments"])


@router.post("/approvals/{request_id}", status_code=status.HTTP_201_CREATED)
@inject
async def upload_file(
    request_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    file: UploadFile = File(...),
    is_reference: bool = False,
    file_service: FileAttachmentService = Depends(Provide[Container.file_attachment_service]),
) -> AttachedFile:
    """결재 요청에 파일 첨부"""
    return await file_service.upload_file(
        request_id=request_id,
        file=file,
        uploaded_by=current_user.id,
        is_reference=is_reference,
    )


@router.get("/approvals/{request_id}")
@inject
async def get_files(
    request_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    file_service: FileAttachmentService = Depends(Provide[Container.file_attachment_service]),
) -> List[AttachedFile]:
    """결재 요청의 첨부파일 목록"""
    return await file_service.get_files(request_id, current_user.id)


@router.get("/{file_id}")
@inject
async def get_file_info(
    file_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    file_service: FileAttachmentService = Depends(Provide[Container.file_attachment_service]),
) -> AttachedFile:
    """첨부파일 정보 조회"""
    return await file_service.get_file_info(file_id, current_user.id)


@router.get("/{file_id}/download")
@inject
async def download_file(
    file_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    file_service: FileAttachmentService = Depends(Provide[Container.file_attachment_service]),
):
    """파일 다운로드"""
    file_info = await file_service.get_file_info(file_id, current_user.id)
    
    if not os.path.exists(file_info.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    return FileResponse(
        path=file_info.file_path,
        filename=file_info.file_name,
        media_type='application/octet-stream'
    )


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_file(
    file_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    file_service: FileAttachmentService = Depends(Provide[Container.file_attachment_service]),
):
    """첨부파일 삭제"""
    await file_service.delete_file(file_id, current_user.id)