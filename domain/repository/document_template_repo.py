from abc import ABCMeta, abstractmethod
from typing import List, Optional
from domain.document_template import DocumentTemplate as DocumentTemplateVo
from infra.db_models.document_template import DocumentTemplate


class IDocumentTemplateRepository(metaclass=ABCMeta):

    @abstractmethod
    async def save(self, template: DocumentTemplateVo) -> None:
        raise NotImplementedError

    @abstractmethod
    async def find_by_id(self, template_id: str) -> Optional[DocumentTemplate]:
        raise NotImplementedError
    
    @abstractmethod
    async def find_all(self) -> List[DocumentTemplate]:
        raise NotImplementedError
    
    @abstractmethod
    async def find_by_category(self, category: str) -> List[DocumentTemplate]:
        raise NotImplementedError
    
    @abstractmethod
    async def find_active_templates(self) -> List[DocumentTemplate]:
        raise NotImplementedError
    
    @abstractmethod
    async def update(self, template: DocumentTemplateVo) -> DocumentTemplate:
        raise NotImplementedError
    
    @abstractmethod
    async def delete(self, template_id: str) -> None:
        raise NotImplementedError