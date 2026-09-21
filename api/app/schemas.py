"""신고 페이로드 계약. docs/01-architecture.md 3절과 같은 내용이다.

기본 모드에서는 이미지가 오지 않는다. 숫자와 해시만 온다.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

Normalized = Annotated[float, Field(ge=0.0, le=1.0)]


class Location(BaseModel):
    lat: Annotated[float, Field(ge=-90, le=90)]
    lon: Annotated[float, Field(ge=-180, le=180)]
    accuracy_m: Annotated[float, Field(ge=0)]
    geohash: Annotated[str, Field(min_length=4, max_length=12)]


class Calibration(BaseModel):
    """기준 패치로 색을 정규화한 결과. 못 찾았으면 색 판정을 믿지 않는다."""

    patch_found: bool
    delta_e_after: float | None = None
    quality: Literal["good", "fair", "poor"]


class Crack(BaseModel):
    width_mm: Annotated[float, Field(ge=0, le=500)]
    # 폭은 항상 오차 범위와 함께 온다. 단일 값만 보여 주면 사용자가 과신한다.
    width_ci_mm: tuple[float, float]
    length_mm: Annotated[float, Field(ge=0)]
    orientation_deg: Annotated[float, Field(ge=0, lt=180)]
    polyline: Annotated[list[tuple[Normalized, Normalized]], Field(max_length=32)]
    confidence: Normalized


class Detection(BaseModel):
    engine: str  # 예: "model@0.3.1-int8" 또는 "classic@0.3.1" — 어느 경로로 돌았는지 남긴다
    cracks: Annotated[list[Crack], Field(max_length=16)]


class ImageMeta(BaseModel):
    w: int
    h: int
    blur_score: Normalized
    exif_stripped: bool


class ReportIn(BaseModel):
    schema_version: Literal[1] = 1
    client_uuid: str  # 오프라인 큐 재전송에서 멱등 처리를 위한 클라이언트 생성 ID
    captured_at: datetime
    location: Location
    calibration: Calibration
    detection: Detection
    image_meta: ImageMeta
    phash: Annotated[str, Field(pattern=r"^[0-9a-f]{16,64}$")]
    note: Annotated[str, Field(max_length=500)] = ""
    consent_image_upload: bool = False


class TrustReason(BaseModel):
    code: str  # 예: "DUPLICATE_NEARBY", "CALIBRATION_POOR"
    delta: float  # 점수에 준 영향 (음수는 감점)
    detail: str


class ReportOut(BaseModel):
    id: str
    state: Literal["pending", "accepted", "held", "merged", "rejected", "closed"]
    trust_score: Annotated[float, Field(ge=0, le=1)]
    # 보류·반려는 반드시 사유가 남는다. 사람에게 설명할 수 없으면 운영에서 못 쓴다.
    trust_reasons: list[TrustReason]
