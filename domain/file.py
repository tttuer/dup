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


class Type(str, Enum):
    VOUCHER = "VOUCHER"
    EXTRA = "EXTRA"


@dataclass
class File:
    id: str
    withdrawn_at: str
    name: str
    updated_at: datetime
    price: int
    lock: bool
    created_at: Optional[datetime] = None
    file_data: Optional[bytes] = None
    file_name: Optional[str] = None
    company: Optional[Company] = None
    type: Optional[Type] = None
