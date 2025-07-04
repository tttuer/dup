import base64
import zlib
from datetime import datetime
from typing import Annotated, Optional, List

from dependency_injector.wiring import inject, Provide
from fastapi import (
    APIRouter,
    status,
    UploadFile,
    Depends,
    Form,
    File,
    HTTPException,
    Query,
)
from pydantic import BaseModel, field_serializer, model_validator

from application.file_service import FileService
from common.auth import CurrentUser
from common.auth import get_current_user
from containers import Container
from domain.file import Company, Type
from domain.responses.file_response import FileResponse

router = APIRouter(prefix="/files", tags=["files"])




ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}


@router.post("", status_code=status.HTTP_201_CREATED)
@inject
async def create_files(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    group_id: str = Form(...),
    withdrawn_at: str = Form(...),
    name: str = Form(...),
    company: Company = Form(...),
    type: Type = Form(...),
    lock: bool = Form(False),
    file_datas: list[UploadFile] = File(...),
    file_service: FileService = Depends(Provide[Container.file_service]),
) -> list[FileResponse]:

    # 파일 타입 검사
    for file in file_datas:
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {file.content_type}",
            )

    files = await file_service.save_files(
        name=name,
        group_id=group_id,
        withdrawn_at=withdrawn_at,
        file_datas=file_datas,
        company=company,
        type=type,
        lock=lock,
    )
    return files


@router.get("/{id}")
@inject
async def find_file(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    id: str,
    file_service: FileService = Depends(Provide[Container.file_service]),
) -> FileResponse:

    return await file_service.find_by_id(id)


@router.get("")
@inject
async def find_files(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    group_id: str,
    is_locked: Optional[bool] = None,
    search: Optional[str] = None,
    search_option: Optional[str] = None,
    start_at: Optional[str] = None,
    end_at: Optional[str] = None,
    company: Optional[Company] = Company.BAEKSUNG,
    type: Optional[Type] = Type.VOUCHER,
    page: int = 1,
    items_per_page: int = 20,
    file_service: FileService = Depends(Provide[Container.file_service]),
) -> tuple[int, int, list[FileResponse]]:
    return await file_service.find_many(
        is_locked=is_locked,
        roles=current_user.roles,
        group_id=group_id,
        search=search,
        search_option=search_option,
        company=company,
        type=type,
        start_at=start_at,
        end_at=end_at,
        page=page,
        items_per_page=items_per_page,
    )


@router.delete("/{id}")
@inject
async def delete_file(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    id: str,
    file_service: FileService = Depends(Provide[Container.file_service]),
):
    await file_service.delete(id)


@router.delete("")
@inject
async def delete_files(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    ids: List[str] = Query(...),
    file_service: FileService = Depends(Provide[Container.file_service]),
):
    await file_service.delete_many(ids)


@router.put("/{id}")
@inject
async def update_file(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    id: str,
    group_id: str = Form(...),
    withdrawn_at: str = Form(...),
    name: str = Form(...),
    lock: bool = Form(...),
    file_data: Optional[UploadFile] = None,
    file_service: FileService = Depends(Provide[Container.file_service]),
) -> FileResponse:

    # 파일 타입 검사
    if file_data and file_data.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file_data.content_type}",
        )

    file = await file_service.update(
        id=id,
        group_id=group_id,
        name=name,
        withdrawn_at=withdrawn_at,
        file_data=file_data,
        lock=lock,
    )
    return file
