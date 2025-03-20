import base64
from datetime import datetime
from typing import Annotated

from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, status, UploadFile, Depends, Form, File
from pydantic import BaseModel, field_serializer

from application.file_service import FileService
from common.auth import CurrentUser
from common.auth import get_current_user
from containers import Container

router = APIRouter(prefix="/files", tags=["files"])


class CreateFileBody(BaseModel):
    withdrawn_at: str
    name: str
    file_datas: list[UploadFile]


class CreateFileResponse(BaseModel):
    id: str
    withdrawn_at: str
    name: str
    created_at: datetime
    updated_at: datetime


class FileResponse(BaseModel):
    id: str
    withdrawn_at: str
    name: str
    created_at: datetime
    updated_at: datetime
    file_data: bytes

    @field_serializer("file_data", when_used="json")
    def encode_file_data(self, file_data: bytes, _info):
        return base64.b64encode(file_data).decode("utf-8")


@router.post("", status_code=status.HTTP_201_CREATED)
@inject
async def create_files(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    withdrawn_at: str = Form(...),
    name: str = Form(...),
    file_datas: list[UploadFile] = File(...),
    file_service: FileService = Depends(Provide[Container.file_service]),
) -> list[CreateFileResponse]:
    files = await file_service.save_files(
        name=name, withdrawn_at=withdrawn_at, file_datas=file_datas
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
