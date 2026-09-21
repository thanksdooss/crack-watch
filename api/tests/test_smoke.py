from fastapi.testclient import TestClient

from api.app.main import app

client = TestClient(app)

SAMPLE = {
    "client_uuid": "11111111-2222-3333-4444-555555555555",
    "captured_at": "2026-09-21T04:12:33Z",
    "location": {"lat": 35.5372, "lon": 129.3167, "accuracy_m": 12, "geohash": "wy7ux5k2"},
    "calibration": {"patch_found": True, "delta_e_after": 2.4, "quality": "good"},
    "detection": {
        "engine": "classic@0.1.0",
        "cracks": [
            {
                "width_mm": 0.84,
                "width_ci_mm": [0.62, 1.10],
                "length_mm": 312,
                "orientation_deg": 71,
                "polyline": [[0.12, 0.33], [0.14, 0.41]],
                "confidence": 0.78,
            }
        ],
    },
    "image_meta": {"w": 4032, "h": 3024, "blur_score": 0.31, "exif_stripped": True},
    "phash": "9f3c1a7b52d6e084",
    "note": "",
    "consent_image_upload": False,
}


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_good_report_is_pending():
    r = client.post("/reports", json=SAMPLE)
    assert r.status_code == 202
    assert r.json()["state"] == "pending"


def test_blurry_uncalibrated_report_is_held():
    bad = {
        **SAMPLE,
        "calibration": {"patch_found": False, "quality": "poor"},
        "image_meta": {**SAMPLE["image_meta"], "blur_score": 0.9},
        "location": {**SAMPLE["location"], "accuracy_m": 120},
    }
    body = client.post("/reports", json=bad).json()
    assert body["state"] == "held"
    assert {x["code"] for x in body["trust_reasons"]} >= {
        "CALIBRATION_MISSING",
        "GPS_IMPRECISE",
        "IMAGE_BLURRY",
    }
