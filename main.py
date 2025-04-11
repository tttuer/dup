from contextlib import asynccontextmanager

from beanie import init_beanie
from fastapi import FastAPI, APIRouter
from fastapi.exceptions import RequestValidationError
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.responses import JSONResponse

from containers import Container
from infra.db_models.file import File
from interface.controller.file_controller import router as file_router
from interface.controller.user_controller import router as user_router
from middleware import add_cors


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    from infra.db_models.user import User

    await init_beanie(database=client.dup, document_models=[File, User])
    yield
    client.close()


app = FastAPI(lifespan=lifespan)

app.container = Container()
add_cors(app)

api_router = APIRouter(prefix="/api")

api_router.include_router(user_router)
api_router.include_router(file_router)

app.include_router(api_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"detail": exc.errors(), "body": exc.body},
    )


# 이 부분 추가해야 디버깅 가능
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=True)
