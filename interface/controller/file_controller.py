from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, status, UploadFile, Depends
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
    created_at: str
    updated_at: str


@router.post("", status_code=status.HTTP_201_CREATED)
@inject
async def create_file(
    file: CreateFileBody,
    file_service: FileService = Depends(Provide[Container.file_service]),
) -> FileResponse:
    file = await file_service.save_file(
        name=file.name, withdrawn_at=file.withdrawn_at, file_datas=file.file_datas
    )

    return file
