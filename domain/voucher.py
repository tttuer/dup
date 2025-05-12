from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class Company(str, Enum):
    BAEKSUNG = "BAEKSUNG"
    PYEONGTAEK = "PYEONGTAEK"
    PARAN = "PARAN"


class SearchOption(str, Enum):
    DESCRIPTION_FILENAME = "DESCRIPTION_FILENAME"
    PRICE = "PRICE"


@dataclass
class Voucher:
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
    file_data: Optional[bytes] = None
    file_name: Optional[str] = None
    company: Optional[Company] = None
