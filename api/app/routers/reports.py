from uuid import uuid4

from fastapi import APIRouter, status

from ..schemas import ReportIn, ReportOut
from ..verify.pipeline import evaluate

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_report(payload: ReportIn) -> ReportOut:
    """신고를 받는다. 저장은 아직 붙지 않았다(2단계 골격)."""
    score, reasons = evaluate(payload, history=[])
    state = "pending" if score >= 0.5 else "held"
    return ReportOut(id=str(uuid4()), state=state, trust_score=score, trust_reasons=reasons)
