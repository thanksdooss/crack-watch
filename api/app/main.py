import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routers import admin, reports, sites


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="균열 감시 API",
    description="시민 신고를 받아 중복·저신뢰 신고를 걸러 낸다. 이미지를 받지 않으며, 안전 여부를 판정하지 않는다.",
    version="0.2.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.environ.get("CORS_ORIGINS", "http://localhost:5178").split(",") if o],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization", "X-Device-Token"],
)
app.include_router(reports.router)
app.include_router(sites.router)
app.include_router(admin.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
