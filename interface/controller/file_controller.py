from datetime import datetime

from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, status, UploadFile, Depends, Form, File
from pydantic import BaseModel

from application.file_service import FileService
from containers import Container

router = APIRouter(prefix="/files")


class CreateFileBody(BaseModel):
    withdrawn_at: str
    name: str
    file_datas: list[UploadFile]


class FileResponse(BaseModel):
    id: str
    withdrawn_at: str
    name: str
    created_at: datetime
    updated_at: datetime


@router.post("", status_code=status.HTTP_201_CREATED)
@inject
async def create_files(
    withdrawn_at: str = Form(...),
    name: str = Form(...),
    file_datas: list[UploadFile] = File(...),
    file_service: FileService = Depends(Provide[Container.file_service]),
) -> list[FileResponse]:
    files = await file_service.save_files(
        name=name, withdrawn_at=withdrawn_at, file_datas=file_datas
    )
    return files
