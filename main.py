from contextlib import asynccontextmanager

from beanie import init_beanie
from fastapi import FastAPI, APIRouter, HTTPException, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.openapi.docs import get_swagger_ui_html
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.responses import JSONResponse

from containers import Container
from interface.controller.file_controller import router as file_router
from interface.controller.user_controller import router as user_router
from interface.controller.whg_controller import router as whg_router
from interface.controller.group_controller import router as group_router
from interface.controller.sync import router as sync_router
from interface.controller.document_template_controller import router as template_router
from interface.controller.approval_controller import router as approval_router
from interface.controller.approval_line_controller import router as approval_line_router
from interface.controller.file_attachment_controller import router as file_attachment_router
from interface.controller.approval_websocket_controller import router as approval_websocket_router
from middleware import add_cors
from infra.db_models.voucher import Voucher
from infra.db_models.user import User
from infra.db_models.file import File
from infra.db_models.group import Group
from infra.db_models.document_template import DocumentTemplate
from infra.db_models.approval_request import ApprovalRequest
from infra.db_models.approval_line import ApprovalLine
from infra.db_models.approval_favorite_group import ApprovalFavoriteGroup
from infra.db_models.approval_history import ApprovalHistory
from infra.db_models.attached_file import AttachedFile
from common.db import client
from utils.settings import settings
from utils.scheduler import start_scheduler, shutdown_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_beanie(
        database=client.dup, document_models=[
            File, User, Voucher, Group, 
            DocumentTemplate, ApprovalRequest, ApprovalLine, ApprovalFavoriteGroup, ApprovalHistory, AttachedFile
        ]
    )
    start_scheduler()
    yield
    client.close()
    shutdown_scheduler()


app = FastAPI(
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None, # 기본 스펙 경로 끄기
)  

app.container = Container()
add_cors(app)

api_router = APIRouter(prefix="/api")

api_router.include_router(user_router)
api_router.include_router(file_router)
api_router.include_router(whg_router)
api_router.include_router(group_router)
api_router.include_router(template_router)
api_router.include_router(approval_router)
api_router.include_router(approval_line_router)
api_router.include_router(file_attachment_router)

app.include_router(api_router)
app.include_router(sync_router)
app.include_router(approval_websocket_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"detail": exc.errors(), "body": exc.body},
    )


security = HTTPBasic()


def verify(credentials: HTTPBasicCredentials = Depends(security)):
    if (
        credentials.username != settings.wehago_id
        or credentials.password != settings.wehago_password
    ):
        raise HTTPException(status_code=401, detail="Unauthorized")


# 보호된 OpenAPI JSON 제공
@app.get("/api/openapi.json", include_in_schema=False)
def secure_openapi(creds: HTTPBasicCredentials = Depends(verify)):
    return JSONResponse(app.openapi())


@app.get("/api/docs", include_in_schema=False)
def secure_docs(credentials: HTTPBasicCredentials = Depends(verify)):
    return get_swagger_ui_html(openapi_url="/api/openapi.json", title="Secure Docs")


# 이 부분 추가해야 디버깅 가능
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=True)
