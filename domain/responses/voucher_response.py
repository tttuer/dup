from datetime import datetime
from typing import Optional
from pydantic import field_serializer
from domain.voucher import Company, VoucherFile
from .base_response import BaseResponse


class VoucherResponse(BaseResponse):
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
    files: Optional[list[VoucherFile]] = None  # VoucherFile 사용
    company: Optional[Company] = None
    
    @field_serializer("files", when_used="json")
    def serialize_files(self, files: Optional[list[VoucherFile]], _info):
        # VoucherFile의 field_serializer가 자동으로 압축 해제 및 base64 인코딩을 처리
        return files
    
    @classmethod
    def from_document(cls, doc) -> "VoucherResponse":
        return cls(
            id=doc.id,
            mn_bungae1=doc.mn_bungae1,
            mn_bungae2=doc.mn_bungae2,
            nm_remark=doc.nm_remark,
            sq_acttax2=doc.sq_acttax2,
            nm_gubn=doc.nm_gubn,
            cd_acctit=doc.cd_acctit,
            year=doc.year,
            cd_trade=doc.cd_trade,
            dt_time=doc.dt_time,
            month=doc.month,
            day=doc.day,
            nm_acctit=doc.nm_acctit,
            dt_insert=doc.dt_insert,
            user_id=doc.user_id,
            da_date=doc.da_date,
            nm_trade=doc.nm_trade,
            no_acct=doc.no_acct,
            voucher_date=doc.voucher_date,
            files=doc.files,
            company=doc.company
        )