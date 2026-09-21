"""신고 검증 — 규칙 기반. 점수와 함께 사유 코드를 낸다.

ML 분류기를 쓰지 않는 이유: 신고를 보류하면 사람에게 이유를 말해야 하고,
지자체가 쓰려면 그 근거가 감사 가능해야 한다.
가중치는 3단계 이후 실제 데이터로 조정한다(현재 값은 초기 가정).
"""

from ..schemas import ReportIn, TrustReason

BASE_SCORE = 1.0


def evaluate(report: ReportIn, history: list[ReportIn]) -> tuple[float, list[TrustReason]]:
    reasons: list[TrustReason] = []
    score = BASE_SCORE

    def penalize(code: str, delta: float, detail: str) -> None:
        nonlocal score
        score += delta
        reasons.append(TrustReason(code=code, delta=delta, detail=detail))

    if not report.calibration.patch_found:
        penalize("CALIBRATION_MISSING", -0.15, "기준 패치를 찾지 못해 색 판정을 신뢰할 수 없다")
    elif report.calibration.quality == "poor":
        penalize("CALIBRATION_POOR", -0.10, "보정 후에도 색차가 커서 색 판정을 보류한다")

    if report.location.accuracy_m > 50:
        penalize("GPS_IMPRECISE", -0.15, f"위치 정확도 {report.location.accuracy_m:.0f}m")

    if report.image_meta.blur_score > 0.6:
        penalize("IMAGE_BLURRY", -0.20, "흔들림이 심해 폭 추정 오차가 커진다")

    if not report.detection.cracks:
        penalize("NO_DETECTION", -0.30, "검출된 균열이 없다")

    # TODO(3단계): 지각 해시 해밍 거리 + 위치 근접으로 중복 판정, 신고자 이력 반영
    return max(0.0, min(1.0, score)), reasons
