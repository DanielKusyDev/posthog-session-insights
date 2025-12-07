from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.config import init_settings
from app.db import init_db


@asynccontextmanager
async def lifespan(app_: FastAPI):
    init_settings()
    await init_db()
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(router)
