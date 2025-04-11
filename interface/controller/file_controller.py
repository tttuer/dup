import base64
import zlib
from datetime import datetime
from typing import Annotated, Optional

from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, status, UploadFile, Depends, Form, File, HTTPException
from pydantic import BaseModel, field_serializer, model_validator

from application.file_service import FileService
from common.auth import CurrentUser
from common.auth import get_current_user
from containers import Container
from domain.file import Company

router = APIRouter(prefix="/files", tags=["files"])


class CreateFileBody(BaseModel):
    withdrawn_at: str
    name: str
    file_datas: list[UploadFile]


class GetFileBody(BaseModel):
    name: str
    start_at: str
    end_at: str
    page: int = 1
    items_per_page: int = 20


class FileResponse(BaseModel):
    id: str
    withdrawn_at: str
    name: str
    price: int
    company: Company
    created_at: datetime
    updated_at: datetime
    file_data: bytes
    file_name: str

    @model_validator(mode="after")
    def decompress_file_data(self):
        try:
            self.file_data = zlib.decompress(self.file_data)
        except zlib.error:
            pass  # 이미 풀려있거나 잘못된 경우는 그냥 넘어감
        return self

    @field_serializer("file_data", when_used="json")
    def encode_file_data(self, file_data: bytes, _info):
        return base64.b64encode(file_data).decode("utf-8")


ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}


@router.post("", status_code=status.HTTP_201_CREATED)
@inject
async def create_files(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    withdrawn_at: str = Form(...),
    name: str = Form(...),
    price: int = Form(...),
    company: Company = Form(...),
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
        withdrawn_at=withdrawn_at,
        file_datas=file_datas,
        price=price,
        company=company,
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
    search: Optional[str] = None,
    search_option: Optional[str] = None,
    start_at: Optional[str] = None,
    end_at: Optional[str] = None,
    company: Optional[Company] = Company.BAEKSUNG,
    page: int = 1,
    items_per_page: int = 30,
    file_service: FileService = Depends(Provide[Container.file_service]),
) -> tuple[int, int, list[FileResponse]]:
    return await file_service.find_many(
        search, search_option, company, start_at, end_at, page, items_per_page
    )
