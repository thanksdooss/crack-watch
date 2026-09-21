"""관리자: 신고 목록, 상태 변경(사유 필수), 지점 병합, 통계.

인증은 단순한 베어러 토큰(ADMIN_TOKEN). 지자체 운영에는 부족하다 — README의 '한계'에 적는다.
"""

import os
from collections import Counter

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import DATABASE_URL, get_db
from ..models import Report, ReviewAction, Site
from ..schemas import AdminAction, ReportOut, Stats, TrustReason

router = APIRouter(prefix="/admin", tags=["admin"])

_TOKEN = os.environ.get("ADMIN_TOKEN") or ("demo-admin" if DATABASE_URL.startswith("sqlite") else None)


def require_admin(authorization: str = Header(default="")) -> str:
    if not _TOKEN:
        raise HTTPException(503, "ADMIN_TOKEN이 설정되지 않았다")
    if authorization != f"Bearer {_TOKEN}":
        raise HTTPException(401, "관리자 토큰이 필요하다")
    return "admin"


TRANSITIONS = {"accept": "accepted", "reject": "rejected", "close": "closed", "hold": "held", "reopen": "pending"}


class AdminReport(ReportOut):
    captured_at: str
    lat: float
    lon: float
    max_width_mm: float | None
    engine: str
    note: str
    device: str


@router.get("/reports")
def list_reports(state: str | None = Query(None), limit: int = Query(200, le=1000),
                 db: Session = Depends(get_db), _: str = Depends(require_admin)) -> list[AdminReport]:
    q = select(Report).order_by(Report.received_at.desc()).limit(limit)
    if state:
        q = q.where(Report.state == state)
    return [AdminReport(id=r.id, site_id=r.site_id, duplicate_of=r.duplicate_of, state=r.state,
                        trust_score=r.trust_score, trust_reasons=[TrustReason(**x) for x in r.trust_reasons],
                        captured_at=r.captured_at.isoformat(), lat=r.lat, lon=r.lon,
                        max_width_mm=r.max_width_mm, engine=r.engine, note=r.note,
                        device=r.device_token[:8]) for r in db.scalars(q)]


@router.post("/reports/{report_id}/action")
def act(report_id: int, body: AdminAction, db: Session = Depends(get_db),
        actor: str = Depends(require_admin)) -> ReportOut:
    r = db.get(Report, report_id)
    if not r:
        raise HTTPException(404, "신고 없음")
    r.state = TRANSITIONS[body.action]
    if r.state in ("accepted", "pending") and r.site_id is None:
        site = Site(lat=r.lat, lon=r.lon, geohash=r.geohash, first_seen=r.captured_at, last_seen=r.captured_at)
        db.add(site)
        db.flush()
        r.site_id = site.id
    db.add(ReviewAction(report_id=r.id, actor=actor, action=body.action, reason=body.reason))
    db.commit()
    return ReportOut(id=r.id, site_id=r.site_id, duplicate_of=r.duplicate_of, state=r.state,
                     trust_score=r.trust_score, trust_reasons=[TrustReason(**x) for x in r.trust_reasons])


@router.post("/sites/{keep_id}/merge/{drop_id}")
def merge_sites(keep_id: int, drop_id: int, db: Session = Depends(get_db),
                actor: str = Depends(require_admin)) -> dict:
    """자동 묶기가 놓친 같은 지점을 사람이 합친다(예: GPS가 크게 튄 경우)."""
    keep, drop = db.get(Site, keep_id), db.get(Site, drop_id)
    if not keep or not drop or keep_id == drop_id:
        raise HTTPException(400, "합칠 지점이 올바르지 않다")
    moved = 0
    for r in list(drop.reports):
        r.site_id = keep.id
        db.add(ReviewAction(report_id=r.id, actor=actor, action="merge_site",
                            reason=f"지점 {drop_id} → {keep_id}"))
        moved += 1
    db.delete(drop)
    db.commit()
    return {"kept": keep_id, "moved_reports": moved}


@router.get("/stats")
def stats(db: Session = Depends(get_db), _: str = Depends(require_admin)) -> Stats:
    reports = db.scalars(select(Report)).all()
    by_state = Counter(r.state for r in reports)
    reviewed_ids = {a.report_id for a in db.scalars(select(ReviewAction)).all()}
    reviewed = [r for r in reports if r.id in reviewed_ids]
    rejected = [r for r in reviewed if r.state == "rejected"]
    auto_held = [r for r in reports if r.trust_score < 0.5 and r.duplicate_of is None]
    held_reviewed = [r for r in reviewed if r.trust_score < 0.5 and r.duplicate_of is None]
    pend_reviewed = [r for r in reviewed if r.trust_score >= 0.5 and r.duplicate_of is None]
    reasons = Counter(x["code"] for r in reports for x in r.trust_reasons)
    n = len(reports) or 1
    return Stats(
        total=len(reports), by_state=dict(by_state),
        auto_held_rate=len(auto_held) / n,
        duplicate_rate=sum(r.duplicate_of is not None for r in reports) / n,
        reviewed=len(reviewed),
        false_report_rate=len(rejected) / len(reviewed) if reviewed else None,
        held_precision=(sum(r.state == "rejected" for r in held_reviewed) / len(held_reviewed)) if held_reviewed else None,
        pending_leak=(sum(r.state == "rejected" for r in pend_reviewed) / len(pend_reviewed)) if pend_reviewed else None,
        reason_counts=dict(reasons),
    )
