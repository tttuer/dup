from typing import Annotated
from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, HTTPException, status, Depends, Response
from fastapi.responses import StreamingResponse
import io

from application.integrity_service import IntegrityService
from application.legal_archive_service import LegalArchiveService
from common.auth import CurrentUser, get_current_user
from containers import Container
from domain.document_integrity import (
    DocumentIntegrityResponse, 
    DocumentIntegrityChainResponse, 
    IntegrityVerificationResponse
)
from domain.responses.paginated_response import PaginatedResponse

router = APIRouter(prefix="/legal", tags=["legal"])


@router.get("/integrity/{request_id}/verify")
@inject
async def verify_document_integrity(
    request_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    integrity_service: IntegrityService = Depends(Provide[Container.integrity_service]),
) -> IntegrityVerificationResponse:
    """문서 무결성 검증"""
    return await integrity_service.verify_document_integrity(request_id, current_user.id)


@router.get("/integrity/{request_id}/chain")
@inject
async def get_integrity_chain(
    request_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    integrity_service: IntegrityService = Depends(Provide[Container.integrity_service]),
) -> DocumentIntegrityChainResponse:
    """문서 무결성 체인 조회"""
    return await integrity_service.get_integrity_chain(request_id, current_user.id)


@router.get("/integrity/tampered")
@inject
async def get_tampered_documents(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    page: int = 1,
    page_size: int = 20,
    integrity_service: IntegrityService = Depends(Provide[Container.integrity_service]),
) -> PaginatedResponse[DocumentIntegrityResponse]:
    """위변조된 문서 목록 조회 (관리자 전용)"""
    items, total = await integrity_service.get_tampered_documents(current_user.id, page, page_size)
    return PaginatedResponse.create(items, total, page, page_size)


@router.post("/integrity/{request_id}/create")
@inject
async def create_document_integrity(
    request_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    integrity_service: IntegrityService = Depends(Provide[Container.integrity_service]),
) -> DocumentIntegrityResponse:
    """문서 무결성 기록 수동 생성 (관리자/테스트 용도)"""
    return await integrity_service.create_document_integrity(request_id, current_user.id)


@router.get("/archive/{request_id}/download")
@inject
async def download_legal_document(
    request_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    legal_archive_service: LegalArchiveService = Depends(Provide[Container.legal_archive_service]),
):
    """법적 문서 다운로드"""
    try:
        content, filename = await legal_archive_service.get_legal_document(request_id, current_user.id)
        
        return StreamingResponse(
            io.BytesIO(content),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=\"{filename}\"",
                "Content-Length": str(len(content))
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download legal document: {str(e)}"
        )


@router.get("/archive/{request_id}/exists")
@inject
async def check_legal_document_exists(
    request_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    legal_archive_service: LegalArchiveService = Depends(Provide[Container.legal_archive_service]),
) -> dict:
    """법적 문서 존재 여부 확인"""
    exists = await legal_archive_service.verify_legal_document_exists(request_id)
    return {"request_id": request_id, "exists": exists}


@router.post("/archive/{request_id}/create")
@inject
async def create_legal_document(
    request_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    legal_archive_service: LegalArchiveService = Depends(Provide[Container.legal_archive_service]),
) -> dict:
    """법적 문서 수동 생성 (관리자/테스트 용도)"""
    try:
        file_id = await legal_archive_service.create_legal_document(request_id, current_user.id)
        return {
            "request_id": request_id,
            "legal_document_id": file_id,
            "message": "Legal document created successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create legal document: {str(e)}"
        )