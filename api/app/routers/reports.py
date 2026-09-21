from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Report
from ..schemas import ReportIn, ReportOut, TrustReason
from ..service import ingest

router = APIRouter(prefix="/reports", tags=["reports"])


def _out(r: Report) -> ReportOut:
    return ReportOut(id=r.id, site_id=r.site_id, duplicate_of=r.duplicate_of, state=r.state,
                     trust_score=r.trust_score,
                     trust_reasons=[TrustReason(**x) for x in r.trust_reasons])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_report(payload: ReportIn, response: Response, db: Session = Depends(get_db),
                  x_device_token: str = Header(default="anonymous", max_length=64)) -> ReportOut:
    """신고 접수. 이미지는 받지 않는다. 같은 client_uuid는 한 번만 처리한다(오프라인 재전송 대비)."""
    existing = db.scalar(select(Report).where(Report.client_uuid == payload.client_uuid))
    if existing:
        response.status_code = status.HTTP_200_OK
        return _out(existing)

    r = ingest(db, payload, x_device_token, datetime.now(timezone.utc))
    return _out(r)


@router.get("/{report_id}")
def get_report(report_id: int, db: Session = Depends(get_db)) -> ReportOut:
    r = db.get(Report, report_id)
    if not r:
        raise HTTPException(404, "신고 없음")
    return _out(r)
