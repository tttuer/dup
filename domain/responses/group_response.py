from pydantic import BaseModel
from domain.file import Company


class GroupResponse(BaseModel):
    id: str
    name: str
    company: Company
    auth_users: list[str] = []
    has_unread_changes: bool = False
    
    @classmethod
    def from_document(cls, doc, has_unread_changes: bool = False) -> "GroupResponse":
        return cls(
            id=doc.id,
            name=doc.name,
            company=doc.company,
            auth_users=doc.auth_users,
            has_unread_changes=has_unread_changes,
        )
