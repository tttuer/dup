import base64
import zlib
from datetime import datetime
from pydantic import field_serializer, model_validator
from domain.file import Company, Type
from .base_response import BaseResponse


class FileResponse(BaseResponse):
    id: str
    group_id: str
    withdrawn_at: str
    name: str
    company: Company
    type: Type
    created_at: datetime
    updated_at: datetime
    file_data: bytes
    file_name: str
    lock: bool

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
    
    @classmethod
    def from_document(cls, doc) -> "FileResponse":
        return cls(
            id=doc.id,
            group_id=doc.group_id,
            withdrawn_at=doc.withdrawn_at,
            name=doc.name,
            company=doc.company,
            type=doc.type,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            file_data=doc.file_data,
            file_name=doc.file_name,
            lock=doc.lock
        )