from abc import ABC, abstractmethod
from domain.wiki import WikiPage, WikiImage

class IWikiRepository(ABC):
    @abstractmethod
    async def save_page(self, page: WikiPage) -> WikiPage:
        pass

    @abstractmethod
    async def update_page(self, page: WikiPage) -> WikiPage:
        pass

    @abstractmethod
    async def get_page(self, page_id: str) -> WikiPage:
        pass

    @abstractmethod
    async def delete_page(self, page_id: str):
        pass

    @abstractmethod
    async def update_descendants_space(self, parent_id: str, is_personal: bool):
        pass

    @abstractmethod
    async def get_public_pages(self) -> list[WikiPage]:
        pass

    @abstractmethod
    async def get_personal_pages(self, author_id: str) -> list[WikiPage]:
        pass

    @abstractmethod
    async def save_image(self, image: WikiImage) -> WikiImage:
        pass

    @abstractmethod
    async def get_image(self, image_id: str) -> WikiImage:
        pass
