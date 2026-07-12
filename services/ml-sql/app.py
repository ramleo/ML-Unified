from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.sql import router
from routers._session_mgr import preload_chinook as _preload_chinook


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _preload_chinook()
    yield


app = FastAPI(title="ml-sql", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)