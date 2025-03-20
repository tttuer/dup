import zlib
from datetime import datetime

from dependency_injector.wiring import inject
from fastapi import UploadFile
from ulid import ULID

from domain.file import File
from domain.repository.file_repo import IFileRepository


class FileService:
    @inject
    def __init__(self, file_repo: IFileRepository):
        self.file_repo = file_repo
        self.ulid = ULID()

    async def compress_pdf(self, file_data: UploadFile) -> bytes:
        raw_data = await file_data.read()
        compress_data = zlib.compress(raw_data)
        return compress_data

    async def save_files(
        self, withdrawn_at: str, name: str, file_datas: list[UploadFile]
    ):
        now = datetime.now()
        files: list[File] = [
            File(
                id=self.ulid.generate(),
                withdrawn_at=withdrawn_at,
                name=name,
                file_data=await self.compress_pdf(file_data),
                created_at=now,
                updated_at=now,
            )
            for file_data in file_datas
        ]

        await self.file_repo.save_all(files)

        return files

    async def find_by_id(self, id: str):
        file = await self.file_repo.find_by_id(id)

        file.file_data = zlib.decompress(file.file_data)
        return file
