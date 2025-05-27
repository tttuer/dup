from typing import Optional
from beanie import Document

from domain.file import Company

class Group(Document):
    name: str
    company: Company