from typing import List
from beanie.operators import And
from domain.wiki import WikiPage as WikiPageVo, WikiImage as WikiImageVo
from infra.db_models.wiki import WikiPage, WikiImage
from domain.repository.wiki_repo import IWikiRepository
from common.exceptions import NotFoundError

class WikiRepository(IWikiRepository):
    async def save_page(self, page: WikiPageVo) -> WikiPageVo:
        db_page = WikiPage(
            id=page.id,
            title=page.title,
            content=page.content,
            parent_id=page.parent_id,
            author_id=page.author_id,
            is_personal=page.is_personal,
            created_at=page.created_at,
            updated_at=page.updated_at
        )
        await db_page.insert()
        return page

    async def update_page(self, page: WikiPageVo) -> WikiPageVo:
        db_page = await WikiPage.get(page.id)
        if not db_page:
            raise NotFoundError("Wiki page not found")
        
        db_page.title = page.title
        db_page.content = page.content
        db_page.parent_id = page.parent_id
        db_page.updated_at = page.updated_at
        
        await db_page.save()
        return page

    async def get_page(self, page_id: str) -> WikiPageVo:
        db_page = await WikiPage.get(page_id)
        if not db_page:
            raise NotFoundError("Wiki page not found")
        # Rename _id to id if model_dump uses alias
        dump = db_page.model_dump(by_alias=True)
        dump["id"] = dump.pop("_id")
        return WikiPageVo(**dump)

    async def delete_page(self, page_id: str):
        db_page = await WikiPage.get(page_id)
        if db_page:
            await db_page.delete()

    async def get_public_pages(self) -> List[WikiPageVo]:
        db_pages = await WikiPage.find(WikiPage.is_personal == False).to_list()
        result = []
        for p in db_pages:
            dump = p.model_dump(by_alias=True)
            dump["id"] = dump.pop("_id")
            result.append(WikiPageVo(**dump))
        return result

    async def get_personal_pages(self, author_id: str) -> List[WikiPageVo]:
        db_pages = await WikiPage.find(
            And(WikiPage.is_personal == True, WikiPage.author_id == author_id)
        ).to_list()
        result = []
        for p in db_pages:
            dump = p.model_dump(by_alias=True)
            dump["id"] = dump.pop("_id")
            result.append(WikiPageVo(**dump))
        return result

    async def save_image(self, image: WikiImageVo) -> WikiImageVo:
        db_image = WikiImage(
            id=image.id,
            file_name=image.file_name,
            content_type=image.content_type,
            file_data=image.file_data,
            uploaded_at=image.uploaded_at
        )
        await db_image.insert()
        return image

    async def get_image(self, image_id: str) -> WikiImageVo:
        db_image = await WikiImage.get(image_id)
        if not db_image:
            raise NotFoundError("Image not found")
        dump = db_image.model_dump(by_alias=True)
        dump["id"] = dump.pop("_id")
        return WikiImageVo(**dump)
