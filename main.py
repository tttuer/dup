from contextlib import asynccontextmanager

from beanie import init_beanie
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.responses import JSONResponse

from infra.db_models.file import File


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    await init_beanie(database=client.dup, document_models=[File])
    yield
    client.close()


app = FastAPI(lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"detail": exc.errors(), "body": exc.body},
    )


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}
