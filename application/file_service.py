import zlib
from datetime import datetime

from bson import Binary
from dependency_injector.wiring import inject
from fastapi import UploadFile
from ulid import ULID

from domain.repository.file_repo import IFileRepository


class FileService:
    @inject
    def __init__(self, file_repo: IFileRepository):
        self.file_repo = file_repo
        self.ulid = ULID()

    async def compress_pdf(self, file_data: UploadFile) -> Binary:
        raw_data = await file_data.read()
        compress_data = zlib.compress(raw_data)
        return Binary(compress_data)

    async def save_file(
        self, withdrawn_at: str, name: str, file_datas: list[UploadFile]
    ):
        now = datetime.now()
        # TODO when save multiple uploaded files at one time, make multiple
        #  files to save
        # file: File = File(
        #     id=self.ulid.generate(),
        #     withdrawn_at=withdrawn_at,
        #     name=name,
        #     file_data=file_data,
        #     created_at=now,
        #     updated_at=now,
        # )
        #
        # await self.file_repo.save(file)
        #
        # return file

    async def find_by_id(self, id: str):
        return await self.file_repo.find_by_id(id)
