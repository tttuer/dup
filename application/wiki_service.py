from fastapi import UploadFile
from ulid import ULID
from application.wiki_security import read_valid_attachment, read_valid_image, sanitize_wiki_content
from domain.repository.wiki_repo import IWikiRepository
from domain.wiki import WikiPage, WikiImage
from utils.time import get_utc_now_naive
from common.exceptions import ValidationError, PermissionError

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

    async def create_page(self, title: str, content: str, author_id: str, is_personal: bool = False, parent_id: str = None, attachments: list[dict] = None) -> WikiPage:
        now = get_utc_now_naive()
        page = WikiPage(
            id=self.ulid.generate(),
            title=title,
            content=sanitize_wiki_content(content),
            parent_id=parent_id,
            author_id=author_id,
            is_personal=is_personal,
            attachments=await self._normalize_attachments(attachments),
            created_at=now,
            updated_at=now
        )
        return await self.wiki_repo.save_page(page)

    def _check_permission(self, page: WikiPage, user_id: str):
        if page.is_personal and page.author_id != user_id:
            raise PermissionError("해당 개인 문서에 접근할 권한이 없습니다.")

    async def update_page(self, page_id: str, title: str, content: str, user_id: str, parent_id: str = None, is_personal: bool = False, attachments: list[dict] = None) -> WikiPage:
        page = await self.wiki_repo.get_page(page_id)
        self._check_permission(page, user_id)
        
        space_changed = page.is_personal != is_personal
        
        page.title = title
        page.content = sanitize_wiki_content(content)
        page.parent_id = parent_id
        page.is_personal = is_personal
        page.attachments = await self._normalize_attachments(attachments)
        page.updated_at = get_utc_now_naive()
        
        updated_page = await self.wiki_repo.update_page(page)
        
        if space_changed:
            await self.wiki_repo.update_descendants_space(page_id, is_personal)
            
        return updated_page

    async def get_page(self, page_id: str, user_id: str) -> WikiPage:
        page = await self.wiki_repo.get_page(page_id)
        self._check_permission(page, user_id)
        return page

    async def delete_page(self, page_id: str, user_id: str):
        page = await self.wiki_repo.get_page(page_id)
        self._check_permission(page, user_id)
        await self.wiki_repo.delete_page(page_id)

    async def reorder_pages(self, items: list, user_id: str):
        await self.wiki_repo.reorder_pages(items)

    async def upload_image(self, file: UploadFile) -> WikiImage:
        file_data = await read_valid_image(file)
        
        image = WikiImage(
            id=self.ulid.generate(),
            file_name=file.filename,
            content_type=file.content_type or "application/octet-stream",
            file_data=file_data,
            uploaded_at=get_utc_now_naive()
        )
        return await self.wiki_repo.save_image(image)

    async def upload_attachment(self, file: UploadFile) -> WikiImage:
        file_data = await read_valid_attachment(file)
        attachment = WikiImage(
            id=self.ulid.generate(),
            file_name=file.filename or "attachment",
            content_type=file.content_type or "application/octet-stream",
            file_data=file_data,
            uploaded_at=get_utc_now_naive(),
        )
        return await self.wiki_repo.save_image(attachment)

    async def get_image(self, image_id: str) -> WikiImage:
        return await self.wiki_repo.get_image(image_id)

    async def _normalize_attachments(self, attachments: list[dict] | None) -> list[dict]:
        """Only persist attachment records previously issued by the upload endpoint."""
        normalized = []
        for attachment in attachments or []:
            if not isinstance(attachment, dict) or not attachment.get("id"):
                raise ValidationError("유효하지 않은 첨부파일 정보입니다.")

            stored_file = await self.wiki_repo.get_image(str(attachment["id"]))
            normalized.append({
                "id": stored_file.id,
                "url": f"/api/wiki/attachments/{stored_file.id}",
                "file_name": stored_file.file_name,
                "size": len(stored_file.file_data),
            })
        return normalized
