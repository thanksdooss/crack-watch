from fastapi import FastAPI

from .routers import reports

app = FastAPI(
    title="균열 감시 API",
    description="시민 신고를 받아 중복·저신뢰 신고를 걸러 낸다. 안전 여부를 판정하지 않는다.",
    version="0.1.0",
)

app.include_router(reports.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
