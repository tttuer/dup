from typing import Optional
from beanie import Document
from pydantic import Field

from domain.file import Company

class Group(Document):
    id: str = Field(alias="_id")
    name: str
    company: Company
    auth_users: list[str]