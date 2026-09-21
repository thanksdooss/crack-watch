import copy
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from api.app.main import app

client = TestClient(app)
ADMIN = {"Authorization": "Bearer test-admin"}
NOW = datetime.now(timezone.utc)

BASE = {
    "captured_at": NOW.isoformat(),
    "location": {"lat": 37.5665, "lon": 126.9780, "accuracy_m": 8, "geohash": "wydm9qy8"},
    "calibration": {"patch_found": True, "delta_e_after": 1.2, "quality": "good"},
    "detection": {"engine": "classic@1", "cracks": [{
        "width_mm": 0.84, "width_ci_mm": [0.62, 1.10], "length_mm": 312, "orientation_deg": 71,
        "polyline": [[0.12, 0.33], [0.14, 0.41]], "confidence": 0.78}]},
    "image_meta": {"w": 1600, "h": 1200, "blur_score": 0.2, "exif_stripped": True},
    "phash": "9f3c1a7b52d6e084",
}


def report(device="dev-a", **over):
    body = copy.deepcopy(BASE)
    body["client_uuid"] = str(uuid.uuid4())
    for k, v in over.items():
        body[k] = v
    return client.post("/reports", json=body, headers={"X-Device-Token": device})


def flip_bits(h: str, n: int) -> str:
    v = int(h, 16)
    for i in range(n):
        v ^= 1 << (i * 5 % 64)
    return f"{v:016x}"


def codes(r):
    return {x["code"] for x in r.json()["trust_reasons"]}


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_good_report_is_pending_and_creates_site():
    r = report()
    assert r.status_code == 202
    assert r.json()["state"] == "pending"
    assert r.json()["site_id"] is not None


def test_idempotent_resend():
    body = copy.deepcopy(BASE) | {"client_uuid": "fixed-uuid"}
    a = client.post("/reports", json=body).json()
    b = client.post("/reports", json=body)
    assert b.status_code == 200 and b.json()["id"] == a["id"]


def test_low_quality_report_is_held_with_reasons():
    r = report(calibration={"patch_found": False, "quality": "poor"},
               image_meta={**BASE["image_meta"], "blur_score": 0.9},
               location={**BASE["location"], "accuracy_m": 120})
    assert r.json()["state"] == "held"
    assert codes(r) >= {"CALIBRATION_MISSING", "GPS_IMPRECISE", "IMAGE_BLURRY"}


def test_same_device_resend_is_merged_as_duplicate():
    a = report().json()
    b = report(phash=flip_bits(BASE["phash"], 5)).json()
    assert b["state"] == "merged" and b["duplicate_of"] == a["id"] and b["site_id"] == a["site_id"]


def test_same_photo_from_other_device_soon_is_duplicate():
    a = report("dev-a").json()
    b = report("dev-b").json()
    assert b["state"] == "merged" and b["duplicate_of"] == a["id"]


def test_later_report_of_same_crack_joins_site_history():
    a = report("dev-a", captured_at=(NOW - timedelta(days=20)).isoformat()).json()
    b = report("dev-b", phash=flip_bits(BASE["phash"], 10)).json()  # 같은 장면, 다른 사람, 20일 뒤
    assert b["state"] == "pending"
    assert b["site_id"] == a["site_id"]


def test_different_wall_nearby_is_a_new_site():
    a = report().json()
    b = report("dev-b", phash="0123456789abcdef").json()  # 근처지만 전혀 다른 장면
    assert b["site_id"] != a["site_id"]


def test_same_photo_far_away_is_flagged_as_reused():
    report()
    far = {"lat": 38.0, "lon": 127.5, "accuracy_m": 8, "geohash": "wyf8jmdw"}  # 약 70km 떨어진 곳
    r = report("dev-b", location=far)
    assert "PHOTO_REUSED_ELSEWHERE" in codes(r)
    assert r.json()["state"] == "held"


def test_future_timestamp_and_implausible_width_are_penalised():
    crack = {**BASE["detection"]["cracks"][0], "width_mm": 80, "width_ci_mm": [70, 90]}
    r = report(captured_at=(NOW + timedelta(hours=2)).isoformat(),
               detection={"engine": "classic@1", "cracks": [crack]})
    assert codes(r) >= {"FUTURE_TIMESTAMP", "IMPLAUSIBLE_WIDTH"}


def test_admin_requires_token():
    assert client.get("/admin/reports").status_code == 401


def test_admin_review_flow_and_stats():
    good = report("dev-a").json()
    bad = report("dev-x", calibration={"patch_found": False, "quality": "poor"},
                 image_meta={**BASE["image_meta"], "blur_score": 0.9},
                 location={**BASE["location"], "accuracy_m": 120}, phash="ffffffffffffffff").json()
    assert client.post(f"/admin/reports/{good['id']}/action", json={"action": "accept", "reason": "현장 확인"},
                       headers=ADMIN).json()["state"] == "accepted"
    assert client.post(f"/admin/reports/{bad['id']}/action", json={"action": "reject", "reason": "벽 아님"},
                       headers=ADMIN).json()["state"] == "rejected"
    s = client.get("/admin/stats", headers=ADMIN).json()
    assert s["total"] == 2 and s["reviewed"] == 2
    assert s["false_report_rate"] == 0.5
    assert s["held_precision"] == 1.0  # 자동 보류한 것은 사람도 반려했다


def test_reason_is_required_for_admin_action():
    r = report().json()
    assert client.post(f"/admin/reports/{r['id']}/action", json={"action": "reject", "reason": ""},
                       headers=ADMIN).status_code == 422


def test_site_history_detects_widening_by_non_overlapping_ranges():
    crack = BASE["detection"]["cracks"][0]
    report("dev-a", captured_at=(NOW - timedelta(days=60)).isoformat(),
           detection={"engine": "classic@1", "cracks": [{**crack, "width_mm": 0.4, "width_ci_mm": [0.3, 0.5]}]})
    r = report("dev-b", phash=flip_bits(BASE["phash"], 10),
               detection={"engine": "classic@1", "cracks": [{**crack, "width_mm": 0.9, "width_ci_mm": [0.7, 1.1]}]}).json()
    site = client.get(f"/sites/{r['site_id']}").json()
    assert site["trend"] == "widening"
    assert site["guidance"] == "전문가 점검 권장"
    assert len(site["history"]) == 2


def test_overlapping_ranges_are_not_called_widening():
    crack = BASE["detection"]["cracks"][0]
    report("dev-a", captured_at=(NOW - timedelta(days=60)).isoformat(),
           detection={"engine": "classic@1", "cracks": [{**crack, "width_mm": 0.20, "width_ci_mm": [0.12, 0.28]}]})
    r = report("dev-b", phash=flip_bits(BASE["phash"], 10),
               detection={"engine": "classic@1", "cracks": [{**crack, "width_mm": 0.24, "width_ci_mm": [0.16, 0.29]}]}).json()
    site = client.get(f"/sites/{r['site_id']}").json()
    assert site["trend"] == "stable"
    assert site["guidance"] == "관찰 필요"


def test_same_scene_tagged_at_another_building_is_flagged():
    """A 건물 벽을 찍고 60m 옆 B 건물 위치로 신고 — 엉뚱한 건물 신고."""
    report("dev-a")
    moved = {**BASE["location"], "lat": BASE["location"]["lat"] + 0.00055}  # 약 61m 북쪽
    r = report("dev-b", phash=flip_bits(BASE["phash"], 9), location=moved)
    assert "SCENE_ELSEWHERE" in codes(r)
    assert r.json()["state"] == "held"
