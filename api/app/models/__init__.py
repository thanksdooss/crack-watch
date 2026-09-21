"""테이블. docs/01-architecture.md 7절.

review_action을 따로 두는 이유: 신고가 보류·반려됐을 때 '왜'를 나중에 설명할 수 있어야 한다.
상태 컬럼만 있으면 이유가 사라진다.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


class Site(Base):
    """같은 벽면의 같은 균열로 묶인 지점. 시간에 따른 폭 변화는 여기 단위로 본다."""

    __tablename__ = "site"
    id: Mapped[int] = mapped_column(primary_key=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    geohash: Mapped[str] = mapped_column(String(12), index=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | watching | closed
    reports: Mapped[list["Report"]] = relationship(back_populates="site")


class Report(Base):
    __tablename__ = "report"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_uuid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("site.id"), index=True)
    duplicate_of: Mapped[int | None] = mapped_column(ForeignKey("report.id"))
    device_token: Mapped[str] = mapped_column(String(64), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    accuracy_m: Mapped[float] = mapped_column(Float)
    geohash: Mapped[str] = mapped_column(String(12), index=True)
    phash: Mapped[str] = mapped_column(String(64))
    engine: Mapped[str] = mapped_column(String(64))
    calibration_quality: Mapped[str] = mapped_column(String(8))
    patch_found: Mapped[bool] = mapped_column()
    blur_score: Mapped[float] = mapped_column(Float)
    max_width_mm: Mapped[float | None] = mapped_column(Float)
    note: Mapped[str] = mapped_column(Text, default="")
    trust_score: Mapped[float] = mapped_column(Float)
    trust_reasons: Mapped[list] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(String(16), index=True)  # pending|accepted|held|merged|rejected|closed
    site: Mapped[Site | None] = relationship(back_populates="reports")
    observations: Mapped[list["Observation"]] = relationship(back_populates="report", cascade="all, delete-orphan")


class Observation(Base):
    """신고 안의 균열 하나."""

    __tablename__ = "observation"
    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("report.id"), index=True)
    width_mm: Mapped[float] = mapped_column(Float)
    width_ci_low: Mapped[float] = mapped_column(Float)
    width_ci_high: Mapped[float] = mapped_column(Float)
    length_mm: Mapped[float] = mapped_column(Float)
    orientation_deg: Mapped[float] = mapped_column(Float)
    polyline: Mapped[list] = mapped_column(JSON)
    confidence: Mapped[float] = mapped_column(Float)
    report: Mapped[Report] = relationship(back_populates="observations")


class ReviewAction(Base):
    __tablename__ = "review_action"
    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("report.id"), index=True)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
