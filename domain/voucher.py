from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, field_serializer
import uuid
import zlib
import base64

class VoucherFile(BaseModel):
    file_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    file_name: str
    file_data: bytes
    uploaded_at: datetime

    @field_validator("file_data", mode="after")
    def decompress_file_data(cls, value: bytes) -> bytes:
        try:
            return zlib.decompress(value)
        except zlib.error:
            return value  # 이미 풀린 경우나 오류는 그냥 넘김

    @field_serializer("file_data", when_used="json")
    def serialize_file_data(self, value: bytes, _info):
        return base64.b64encode(value).decode("utf-8") if value else None

class Company(str, Enum):
    BAEKSUNG = "BAEKSUNG"
    PYEONGTAEK = "PYEONGTAEK"
    PARAN = "PARAN"


class SearchOption(str, Enum):
    NM_ACCTIT = "NM_ACCTIT" # 계정과목
    NM_TRADE = "NM_TRADE" # 거래처
    NM_REMARK = "NM_REMARK" # 적요


class Voucher(BaseModel):
    id: str
    mn_bungae1: Optional[float] = None
    mn_bungae2: Optional[float] = None
    nm_remark: Optional[str] = None
    sq_acttax2: Optional[int] = None
    nm_gubn: Optional[str] = None
    cd_acctit: Optional[str] = None
    year: Optional[str] = None
    cd_trade: Optional[str] = None
    dt_time: Optional[datetime] = None
    month: Optional[str] = None
    day: Optional[str] = None
    nm_acctit: Optional[str] = None
    dt_insert: Optional[datetime] = None
    user_id: Optional[str] = None
    da_date: Optional[str] = None
    nm_trade: Optional[str] = None  
    no_acct: Optional[int] = None
    voucher_date: Optional[str] = None
    files: List[VoucherFile] = Field(default_factory=list)
    company: Optional[Company] = None   
