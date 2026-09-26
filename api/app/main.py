import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routers import admin, reports, sites


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    # 데모 배포용: 비어 있으면 합성 신고를 넣어 지도·관리자 화면을 체험할 수 있게 한다.
    # Render 무료 요금제는 배포 전 명령(preDeployCommand)을 쓸 수 없어 여기서 한다.
    if os.environ.get("SEED_DEMO", "").lower() in ("1", "true", "yes"):
        from api.sim.seed_demo import main as seed_demo

        try:
            seed_demo()
        except Exception as e:  # 데모 데이터 때문에 서버가 안 뜨는 일은 없어야 한다
            print(f"[seed_demo] 건너뜀: {e}")
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
