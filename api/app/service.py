"""신고 접수의 핵심 — 라우터와 시뮬레이션이 같이 쓴다(시뮬레이션은 '현재 시각'을 바꿔 가며 부른다)."""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Observation, Report, Site
from .schemas import ReportIn
from .verify.pipeline import evaluate


def ingest(db: Session, payload: ReportIn, device_token: str, now: datetime) -> Report:
    d = evaluate(db, payload, device_token, now)
    site_id = d.site_id
    if site_id is None and d.state == "pending":
        site = Site(lat=payload.location.lat, lon=payload.location.lon, geohash=payload.location.geohash,
                    first_seen=payload.captured_at, last_seen=payload.captured_at)
        db.add(site)
        db.flush()
        site_id = site.id
    widths = [c.width_mm for c in payload.detection.cracks]
    r = Report(
        client_uuid=payload.client_uuid, site_id=site_id, duplicate_of=d.duplicate_of,
        device_token=device_token, captured_at=payload.captured_at, received_at=now,
        lat=payload.location.lat, lon=payload.location.lon, accuracy_m=payload.location.accuracy_m,
        geohash=payload.location.geohash, phash=payload.phash, engine=payload.detection.engine,
        calibration_quality=payload.calibration.quality, patch_found=payload.calibration.patch_found,
        blur_score=payload.image_meta.blur_score, max_width_mm=max(widths) if widths else None,
        note=payload.note, trust_score=d.score, trust_reasons=[x.model_dump() for x in d.reasons],
        state=d.state,
    )
    r.observations = [
        Observation(width_mm=c.width_mm, width_ci_low=c.width_ci_mm[0], width_ci_high=c.width_ci_mm[1],
                    length_mm=c.length_mm, orientation_deg=c.orientation_deg,
                    polyline=[list(p) for p in c.polyline], confidence=c.confidence)
        for c in payload.detection.cracks
    ]
    db.add(r)
    if any(x.code == "FLOODING" for x in d.reasons):
        # 도배가 감지되면 같은 기기가 직전 한 시간에 보낸, 아직 통과 상태인 신고도 보류한다.
        # 기준(6건)에 닿기 전의 신고들이 그대로 통과되는 틈을 막는다.
        for prev in db.scalars(select(Report).where(
                Report.device_token == device_token, Report.state == "pending",
                Report.received_at >= now - timedelta(hours=1))):
            prev.state = "held"
            prev.trust_reasons = prev.trust_reasons + [{
                "code": "FLOODING_RETRO", "delta": 0.0,
                "detail": "같은 기기의 도배가 감지되어 이 신고도 소급 보류"}]
    db.commit()
    return r
