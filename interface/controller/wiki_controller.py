from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File as FastAPIFile
from fastapi.responses import Response
from pydantic import BaseModel
from dependency_injector.wiring import inject, Provide
from containers import Container
from application.wiki_service import WikiService
from common.auth import get_current_user, CurrentUser
from typing import Annotated
from domain.wiki import PageReorderItem

router = APIRouter(prefix="/wiki", tags=["wiki"])

class PageCreateRequest(BaseModel):
    title: str
    content: str
    parent_id: Optional[str] = None
    is_personal: bool = False
    attachments: list[dict] = []

class PageUpdateRequest(BaseModel):
    title: str
    content: str
    parent_id: Optional[str] = None
    is_personal: bool
    attachments: list[dict] = []

class PageReorderRequest(BaseModel):
    items: list[PageReorderItem]

@router.get("/tree")
@inject
async def get_wiki_tree(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    wiki_service: WikiService = Depends(Provide[Container.wiki_service])
):
    pages = await wiki_service.get_tree()
    return pages

@router.get("/personal")
@inject
async def get_personal_tree(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    wiki_service: WikiService = Depends(Provide[Container.wiki_service])
):
    pages = await wiki_service.get_personal_tree(current_user.id)
    return pages

@router.put("/reorder")
@inject
async def reorder_pages(
    req: PageReorderRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    wiki_service: WikiService = Depends(Provide[Container.wiki_service])
):
    await wiki_service.reorder_pages(req.items, current_user.id)
    return {"message": "Reordered successfully"}

@router.post("")
@inject
async def create_page(
    req: PageCreateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    wiki_service: WikiService = Depends(Provide[Container.wiki_service])
):
    return await wiki_service.create_page(
        title=req.title,
        content=req.content,
        author_id=current_user.id,
        is_personal=req.is_personal,
        parent_id=req.parent_id,
        attachments=req.attachments
    )

@router.get("/{page_id}")
@inject
async def get_page(
    page_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    wiki_service: WikiService = Depends(Provide[Container.wiki_service])
):
    return await wiki_service.get_page(page_id, current_user.id)

@router.put("/{page_id}")
@inject
async def update_page(
    page_id: str,
    req: PageUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    wiki_service: WikiService = Depends(Provide[Container.wiki_service])
):
    return await wiki_service.update_page(
        page_id=page_id,
        title=req.title,
        content=req.content,
        user_id=current_user.id,
        parent_id=req.parent_id,
        is_personal=req.is_personal,
        attachments=req.attachments
    )

@router.delete("/{page_id}")
@inject
async def delete_page(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    page_id: str,
    wiki_service: WikiService = Depends(Provide[Container.wiki_service])
):
    await wiki_service.delete_page(page_id, current_user.id)
    return {"message": "deleted"}

@router.post("/upload")
@inject
async def upload_image(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    file: UploadFile = FastAPIFile(...),
    wiki_service: WikiService = Depends(Provide[Container.wiki_service])
):
    image = await wiki_service.upload_image(file)
    return {"id": image.id, "url": f"/api/wiki/images/{image.id}"}

@router.get("/images/{image_id}")
@inject
async def get_image(
    image_id: str,
    wiki_service: WikiService = Depends(Provide[Container.wiki_service])
):
    image = await wiki_service.get_image(image_id)
    return Response(content=image.file_data, media_type=image.content_type)

@router.post("/attachments/upload")
@inject
async def upload_attachment(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    file: UploadFile = FastAPIFile(...),
    wiki_service: WikiService = Depends(Provide[Container.wiki_service])
):
    image = await wiki_service.upload_image(file)
    return {
        "id": image.id, 
        "url": f"/api/wiki/attachments/{image.id}", 
        "file_name": file.filename, 
        "size": file.size if hasattr(file, "size") else 0
    }

@router.get("/attachments/{file_id}")
@inject
async def get_attachment(
    file_id: str,
    wiki_service: WikiService = Depends(Provide[Container.wiki_service])
):
    image = await wiki_service.get_image(file_id)
    import urllib.parse
    encoded_name = urllib.parse.quote(image.file_name)
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}"}
    return Response(content=image.file_data, media_type=image.content_type, headers=headers)
