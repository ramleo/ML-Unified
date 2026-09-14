from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from routers._guard import cors_kwargs, guard
from routers.sql import router
from routers._session_mgr import preload_chinook as _preload_chinook


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _preload_chinook()
    yield


app = FastAPI(title="ml-sql", version="1.0.0", lifespan=lifespan)
# Order matters: the last middleware added runs first. CORS goes outermost so
# a 403/429 from the guard still carries CORS headers and the browser can
# read the message instead of reporting an opaque network error.
app.add_middleware(BaseHTTPMiddleware, dispatch=guard)
app.add_middleware(CORSMiddleware, **cors_kwargs())
app.include_router(router)
