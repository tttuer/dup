from fastapi import UploadFile
from ulid import ULID
from domain.repository.wiki_repo import IWikiRepository
from domain.wiki import WikiPage, WikiImage
from utils.time import get_utc_now_naive
from common.exceptions import ValidationError

class WikiService:
    def __init__(self, wiki_repo: IWikiRepository):
        self.wiki_repo = wiki_repo
        self.ulid = ULID()

    async def get_tree(self) -> list[WikiPage]:
        # Return all public pages for building the tree
        return await self.wiki_repo.get_public_pages()

    async def get_personal_tree(self, user_id: str) -> list[WikiPage]:
        # Return personal pages for the user
        return await self.wiki_repo.get_personal_pages(user_id)

    async def create_page(self, title: str, content: str, author_id: str, is_personal: bool = False, parent_id: str = None) -> WikiPage:
        now = get_utc_now_naive()
        page = WikiPage(
            id=self.ulid.generate(),
            title=title,
            content=content,
            parent_id=parent_id,
            author_id=author_id,
            is_personal=is_personal,
            created_at=now,
            updated_at=now
        )
        return await self.wiki_repo.save_page(page)

    async def update_page(self, page_id: str, title: str, content: str, parent_id: str = None) -> WikiPage:
        page = await self.wiki_repo.get_page(page_id)
        page.title = title
        page.content = content
        page.parent_id = parent_id
        page.updated_at = get_utc_now_naive()
        
        return await self.wiki_repo.update_page(page)

    async def get_page(self, page_id: str) -> WikiPage:
        return await self.wiki_repo.get_page(page_id)

    async def delete_page(self, page_id: str):
        await self.wiki_repo.delete_page(page_id)

    async def upload_image(self, file: UploadFile) -> WikiImage:
        file_data = await file.read()
        if not file_data:
            raise ValidationError("Empty file")
        
        image = WikiImage(
            id=self.ulid.generate(),
            file_name=file.filename,
            content_type=file.content_type or "application/octet-stream",
            file_data=file_data,
            uploaded_at=get_utc_now_naive()
        )
        return await self.wiki_repo.save_image(image)

    async def get_image(self, image_id: str) -> WikiImage:
        return await self.wiki_repo.get_image(image_id)
