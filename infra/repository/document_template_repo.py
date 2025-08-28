from typing import List, Optional

from domain.repository.document_template_repo import IDocumentTemplateRepository
from domain.document_template import DocumentTemplate as DocumentTemplateVo
from infra.db_models.document_template import DocumentTemplate
from infra.repository.base_repo import BaseRepository


class DocumentTemplateRepository(BaseRepository[DocumentTemplate], IDocumentTemplateRepository):
    def __init__(self):
        super().__init__(DocumentTemplate)

    async def save(self, template: DocumentTemplateVo) -> None:
        new_template = DocumentTemplate(
            id=template.id,
            name=template.name,
            description=template.description,
            category=template.category,
            document_prefix=template.document_prefix,
            default_approval_steps=template.default_approval_steps,
            is_active=template.is_active,
            created_at=template.created_at,
            updated_at=template.updated_at,
        )
        await new_template.insert()

    async def find_by_id(self, template_id: str) -> Optional[DocumentTemplate]:
        return await DocumentTemplate.get(template_id)
    
    async def find_all(self) -> List[DocumentTemplate]:
        templates = await DocumentTemplate.find().to_list()
        return templates or []
    
    async def find_by_category(self, category: str) -> List[DocumentTemplate]:
        templates = await DocumentTemplate.find(DocumentTemplate.category == category).to_list()
        return templates or []
    
    async def find_active_templates(self) -> List[DocumentTemplate]:
        templates = await DocumentTemplate.find(DocumentTemplate.is_active == True).to_list()
        return templates or []
    
    async def update(self, template: DocumentTemplateVo) -> DocumentTemplate:
        db_template = await self.find_by_id_or_raise(template.id, "DocumentTemplate")
        db_template.name = template.name
        db_template.description = template.description
        db_template.category = template.category
        db_template.document_prefix = template.document_prefix
        db_template.default_approval_steps = template.default_approval_steps
        db_template.is_active = template.is_active
        db_template.updated_at = template.updated_at
        
        return await db_template.save()
    
    async def delete(self, template_id: str) -> None:
        await self.delete_by_id(template_id)