from typing import Optional
from beanie import Document
from pydantic import BaseModel, Field
from datetime import datetime
from domain.voucher import Company, VoucherFile


class Voucher(Document):
    id: str = Field(alias="_id")
    mn_bungae1: Optional[float] = None # 차변 금액
    mn_bungae2: Optional[float] = None # 대변 금액
    nm_remark: Optional[str] = None # 적요
    sq_acttax2: Optional[int] = None
    nm_gubn: Optional[str] = None
    cd_acctit: Optional[str] = None
    year: Optional[str] = None
    cd_trade: Optional[str] = None
    dt_time: Optional[datetime] = None
    month: Optional[str] = None
    day: Optional[str] = None
    nm_acctit: Optional[str] = None # 계정과목
    dt_insert: Optional[datetime] = None
    user_id: Optional[str] = None
    da_date: Optional[str] = None
    nm_trade: Optional[str] = None  # 거래처
    no_acct: Optional[int] = None # 전표 묶는 기준
    voucher_date: Optional[str] = None
    files: Optional[list[VoucherFile]] = None
    company: Optional[Company] = Field(default=None)

    class Settings:
        name = "vouchers"  # MongoDB collection name
