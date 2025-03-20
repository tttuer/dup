from contextlib import asynccontextmanager

from beanie import init_beanie
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.responses import JSONResponse

from containers import Container
from infra.db_models.file import File
from interface.controller.file_controller import router as file_router
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

app.include_router(user_router)
app.include_router(file_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"detail": exc.errors(), "body": exc.body},
    )
