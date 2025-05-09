import zlib
from fastapi import UploadFile


class Pdf:
    @staticmethod
    async def compress(file_data: UploadFile) -> bytes:
        raw_data = await file_data.read()
        compress_data = zlib.compress(raw_data)
        return compress_data