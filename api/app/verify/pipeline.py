"""신고 검증 — 규칙 기반. 점수와 함께 사유 코드를 낸다.

ML 분류기를 쓰지 않는 이유: 신고를 보류하면 사람에게 이유를 말해야 하고, 지자체가 쓰려면
그 근거가 감사 가능해야 한다. 규칙과 임계값은 rules.py 한곳에 있다.

흐름
1. 근처(반경 15~50m) 기존 신고 중 같은 장면(지각 해시가 가까운 것)이 있으면 그 지점(site)에 묶는다.
2. 같은 장면을 같은 기기가 하루 안에, 또는 누구든 거의 같은 사진을 2시간 안에 또 보냈으면 '중복'.
3. 같은 사진이 멀리 떨어진 다른 위치로 올라왔으면 '사진 재사용' — 장난의 전형.
   같은 장면(다시 찍은 사진)이 근처의 다른 위치(15m 밖, 500m 안)에 이미 있으면 '위치 불일치' —
   A 건물을 찍고 B 건물 위치로 신고한 경우(엉뚱한 건물 신고).
4. 품질·정합성 감점 → 점수가 기준 아래면 자동 보류(삭제하지 않는다. 사람이 되돌릴 수 있게).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Report
from ..schemas import ReportIn, TrustReason
from .rules import RULES, Rules


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def hamming(a: str, b: str) -> int:
    if len(a) != len(b):
        return 64
    return bin(int(a, 16) ^ int(b, 16)).count("1")


@dataclass
class Decision:
    score: float
    reasons: list[TrustReason]
    state: str
    site_id: int | None  # None이면 새 지점
    duplicate_of: int | None
    nearby: list[tuple[int, float, int]] = field(default_factory=list)  # (report_id, 거리 m, 해밍)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def evaluate(db: Session, r: ReportIn, device_token: str, now: datetime | None = None,
             rules: Rules = RULES) -> Decision:
    now = now or datetime.now(timezone.utc)
    reasons: list[TrustReason] = []
    score = 1.0

    def adjust(code: str, delta: float, detail: str) -> None:
        nonlocal score
        score += delta
        reasons.append(TrustReason(code=code, delta=delta, detail=detail))

    # ---- 1. 근처 같은 장면 찾기 -------------------------------------------------
    # 후보는 위경도 범위로 뽑는다. 처음엔 geohash 앞 5자리가 같은 '칸'에서만 찾았는데,
    # 칸 경계 바로 너머의 이웃을 못 봐서 '엉뚱한 건물' 검사가 새었다(시뮬레이션에서 발견).
    lat, lon = r.location.lat, r.location.lon
    dlat = rules.scene_elsewhere_m / 111_320
    dlon = dlat / max(0.2, math.cos(math.radians(lat)))
    cands = db.scalars(select(Report).where(
        Report.lat.between(lat - dlat, lat + dlat), Report.lon.between(lon - dlon, lon + dlon),
        Report.state != "rejected")).all()
    radius = min(rules.max_radius_m, max(rules.site_radius_m, r.location.accuracy_m))
    nearby, near50, elsewhere = [], [], []
    for c in cands:
        d = haversine_m(lat, lon, c.lat, c.lon)
        h = hamming(r.phash, c.phash)
        if d <= radius:
            nearby.append((c, d, h))
        if d <= rules.max_radius_m:
            near50.append((c, d, h))
        elif d <= rules.scene_elsewhere_m and h <= rules.scene_elsewhere_hamming and c.state != "held":
            elsewhere.append((c, d, h))
    same_scene = sorted((x for x in nearby if x[2] <= rules.same_scene_hamming), key=lambda x: (x[2], x[1]))
    site_id = next((c.site_id for c, _, _ in same_scene if c.site_id), None)

    # ---- 2. 중복 --------------------------------------------------------------
    # 중복은 50m까지 본다: 같은 사람이 몇 분 뒤 다시 보내도 GPS가 흔들려 15m를 넘길 수 있다.
    duplicate_of = None
    captured = _aware(r.captured_at)
    for c, _, h in sorted(near50, key=lambda x: (x[2], x[1])):
        dt_h = abs((captured - _aware(c.captured_at)).total_seconds()) / 3600
        if c.device_token == device_token and h <= rules.same_scene_hamming \
                and dt_h <= rules.duplicate_same_device_hours:
            duplicate_of = c.duplicate_of or c.id
            site_id = site_id or c.site_id
            reasons.append(TrustReason(code="DUPLICATE_SAME_DEVICE", delta=0.0,
                                       detail=f"같은 기기가 {dt_h:.1f}시간 안에 같은 장면을 다시 보냄"))
            break
        if h <= rules.duplicate_hamming and dt_h <= rules.duplicate_any_device_hours:
            duplicate_of = c.duplicate_of or c.id
            site_id = site_id or c.site_id
            reasons.append(TrustReason(code="DUPLICATE_SAME_PHOTO", delta=0.0,
                                       detail=f"거의 같은 사진(해밍 {h})이 {dt_h:.1f}시간 안에 이미 접수됨"))
            break

    # ---- 3. 사진 재사용 / 위치 불일치 -------------------------------------------
    # 같은 사진을 다시 저장하면 해시가 0~4비트 달라진다(측정값). 그래서 '완전히 같은 해시'가
    # 아니라 해밍 8 이하로 찾는다. 전체 신고를 훑는다 — 수만 건 규모에선 BK-트리나
    # PostgreSQL bit_count 색인이 필요하다(README 한계).
    far = []
    for rid, rlat, rlon, rph in db.execute(select(Report.id, Report.lat, Report.lon, Report.phash)):
        if hamming(r.phash, rph) <= rules.duplicate_hamming and \
                haversine_m(lat, lon, rlat, rlon) > rules.reuse_far_m:
            far.append(rid)
    if far:
        adjust("PHOTO_REUSED_ELSEWHERE", -0.6,
               f"거의 같은 사진이 {len(far)}건, {rules.reuse_far_m:.0f}m 넘게 떨어진 다른 위치로 이미 접수됨")
    elif elsewhere and not same_scene:
        c, d, h = min(elsewhere, key=lambda x: x[1])
        adjust("SCENE_ELSEWHERE", -0.6,
               f"같은 장면(해밍 {h})이 {d:.0f}m 떨어진 다른 위치로 이미 접수됨 — 위치가 틀렸을 수 있다")

    # ---- 4. 품질·정합성 --------------------------------------------------------
    if not r.calibration.patch_found:
        adjust("CALIBRATION_MISSING", -0.15, "기준 카드를 찾지 못해 폭(mm)과 색을 믿을 수 없다")
    elif r.calibration.quality == "poor":
        adjust("CALIBRATION_POOR", -0.10, "보정 후에도 색차가 커서 색 판정을 보류한다")
    if r.location.accuracy_m > rules.gps_imprecise_m:
        adjust("GPS_IMPRECISE", -0.15, f"위치 정확도 {r.location.accuracy_m:.0f}m")
    if r.image_meta.blur_score > rules.blur_max:
        adjust("IMAGE_BLURRY", -0.20, "흔들림이 심해 폭 추정 오차가 커진다")
    if not r.detection.cracks:
        adjust("NO_DETECTION", -0.50, "검출된 균열이 없다 — 검출기가 놓쳤을 수도 있어 사람이 확인한다")
    if any(c.width_mm > rules.max_plausible_width_mm for c in r.detection.cracks):
        adjust("IMPLAUSIBLE_WIDTH", -0.30, f"폭이 {rules.max_plausible_width_mm:.0f}mm를 넘는다 — 균열이 아니라 줄눈·틈일 가능성")
    skew_min = (captured - now).total_seconds() / 60
    if skew_min > rules.future_skew_min:
        adjust("FUTURE_TIMESTAMP", -0.30, f"촬영 시각이 현재보다 {skew_min:.0f}분 뒤")
    age_days = (now - captured).total_seconds() / 86400
    if age_days > rules.stale_days:
        adjust("STALE_PHOTO", -0.20, f"{age_days:.0f}일 전 사진 — 현재 상태와 다를 수 있다")

    recent = db.scalar(select(func.count()).select_from(Report).where(
        Report.device_token == device_token, Report.received_at >= now - timedelta(hours=1)))
    if recent and recent >= rules.flood_per_hour:
        # 도배는 보류까지 간다. 봉사자의 몰아 조사도 걸리지만 보류는 삭제가 아니라 사람 확인 대기열이다.
        adjust("FLOODING", -0.60, f"같은 기기에서 한 시간에 {recent}건")
    reviewed = db.scalars(select(Report.state).where(
        Report.device_token == device_token, Report.state.in_(("accepted", "rejected", "closed")))).all()
    if len(reviewed) >= rules.device_min_reviewed:
        rate = sum(s == "rejected" for s in reviewed) / len(reviewed)
        if rate >= rules.device_reject_rate:
            adjust("DEVICE_HISTORY", -0.30, f"이 기기의 과거 신고 {len(reviewed)}건 중 {rate:.0%} 반려")

    if site_id is not None and duplicate_of is None:
        others = {c.device_token for c, _, _ in same_scene if c.state == "accepted"} - {device_token}
        if others:
            adjust("CORROBORATED", +0.10, f"같은 지점에 다른 시민 {len(others)}명의 확인된 신고가 있다")

    score = max(0.0, min(1.0, score))
    state = "merged" if duplicate_of else ("held" if score < rules.hold_below else "pending")
    return Decision(score=score, reasons=reasons, state=state, site_id=site_id,
                    duplicate_of=duplicate_of, nearby=[(c.id, d, h) for c, d, h in nearby])
