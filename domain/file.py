from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Company(str, Enum):
    BAEKSUNG = "BAEKSUNG"
    PYEONGTAEK = "PYEONGTAEK"
    PARAN = "PARAN"


class SearchOption(str, Enum):
    DESCRIPTION_FILENAME = "DESCRIPTION_FILENAME"
    PRICE = "PRICE"


@dataclass
class File:
    id: str
    withdrawn_at: str
    name: str
    created_at: datetime
    updated_at: datetime
    file_data: bytes
    file_name: str
    price: int
    company: Company
