from pydantic import BaseModel
from domain.file import Company


class GroupResponse(BaseModel):
    id: str
    name: str
    company: Company
    auth_users: list[str] = []
    
    @classmethod
    def from_document(cls, doc) -> "GroupResponse":
        return cls(
            id=doc.id,
            name=doc.name,
            company=doc.company,
            auth_users=doc.auth_users
        )