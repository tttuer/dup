from contextlib import asynccontextmanager

from beanie import init_beanie
from fastapi import FastAPI, APIRouter
from fastapi.exceptions import RequestValidationError
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles

from containers import Container
from infra.db_models.file import File
from interface.controller.file_controller import router as file_router
from interface.controller.page_controller import router as page_router
from interface.controller.user_controller import router as user_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    from infra.db_models.user import User

    await init_beanie(database=client.dup, document_models=[File, User])
    yield
    client.close()


app = FastAPI(lifespan=lifespan)

app.container = Container()

api_router = APIRouter(prefix="/api")

api_router.include_router(user_router)
api_router.include_router(file_router)

app.include_router(page_router)
app.include_router(api_router)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"detail": exc.errors(), "body": exc.body},
    )
