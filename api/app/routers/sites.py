"""지도와 이력. 같은 지점의 신고를 시간순으로 보고, 폭이 넓어지는지 판단한다.

'넓어지는 중'은 오차 범위로 판단한다: 가장 최근 폭의 범위 하단이 처음 폭의 범위 상단보다
크면(범위가 겹치지 않으면) 넓어졌다고 본다. 대표값만 비교하면 측정 흔들림을 변화로 오인한다.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Report, Site
from ..schemas import HistoryPoint, SiteDetail, SiteOut

router = APIRouter(prefix="/sites", tags=["sites"])
VISIBLE = ("pending", "accepted", "closed")
EXPERT_MM = 0.3  # shared/pipeline.json measure.guidance.expertReviewMm와 같은 값


def _history(site: Site) -> list[HistoryPoint]:
    pts = []
    for r in sorted(site.reports, key=lambda r: r.captured_at):
        if r.state not in VISIBLE:
            continue
        best = max(r.observations, key=lambda o: o.width_mm, default=None)
        pts.append(HistoryPoint(report_id=r.id, captured_at=r.captured_at, state=r.state,
                                max_width_mm=best.width_mm if best else None,
                                max_width_ci_mm=(best.width_ci_low, best.width_ci_high) if best else None,
                                engine=r.engine))
    return pts


def _trend(h: list[HistoryPoint]) -> tuple[str, str]:
    w = [p for p in h if p.max_width_ci_mm]
    if len(w) < 2:
        return "unknown", "비교할 이전 기록이 없습니다"
    first, last = w[0], w[-1]
    days = max(1, (last.captured_at - first.captured_at).days)
    if last.max_width_ci_mm[0] > first.max_width_ci_mm[1]:
        return "widening", (f"{days}일 사이 {first.max_width_mm:.2f} → {last.max_width_mm:.2f}mm. "
                            "오차 범위가 겹치지 않을 만큼 넓어졌습니다")
    return "stable", f"{days}일 사이 오차 범위 안에서 변화가 없습니다"


def _summary(site: Site) -> SiteOut:
    h = _history(site)
    trend, _ = _trend(h)
    latest = next((p for p in reversed(h) if p.max_width_mm is not None), None)
    if latest is None:
        guidance = "판정 보류"
    elif trend == "widening" or (latest.max_width_ci_mm and latest.max_width_ci_mm[1] >= EXPERT_MM):
        guidance = "전문가 점검 권장"
    else:
        guidance = "관찰 필요"
    return SiteOut(id=site.id, lat=site.lat, lon=site.lon, status=site.status, report_count=len(h),
                   latest_width_mm=latest.max_width_mm if latest else None, trend=trend, guidance=guidance)


@router.get("")
def list_sites(min_lat: float = Query(-90), max_lat: float = Query(90), min_lon: float = Query(-180),
               max_lon: float = Query(180), db: Session = Depends(get_db)) -> list[SiteOut]:
    sites = db.scalars(select(Site).where(Site.lat.between(min_lat, max_lat),
                                          Site.lon.between(min_lon, max_lon))).all()
    return [s for s in (_summary(x) for x in sites) if s.report_count > 0]


@router.get("/{site_id}")
def site_detail(site_id: int, db: Session = Depends(get_db)) -> SiteDetail:
    site = db.get(Site, site_id)
    if not site:
        raise HTTPException(404, "지점 없음")
    h = _history(site)
    _, detail = _trend(h)
    return SiteDetail(**_summary(site).model_dump(), history=h, trend_detail=detail)
