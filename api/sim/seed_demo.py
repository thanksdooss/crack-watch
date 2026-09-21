"""데모용 DB 채우기 — 검증 시뮬레이션과 같은 신고 흐름(정답 라벨 포함)을 설정된 DB에 넣는다.

    DATABASE_URL=... python -m api.sim.seed_demo

모두 합성 신고다(실제 건물·실제 신고 아님). 좌표는 중립 지점 주변에 무작위로 흩어져 있다.
지도·이력·관리자 화면을 로그인 없이 체험할 수 있게 하려는 용도.
"""

from __future__ import annotations

import json
import random
import uuid

from api.sim.verification import ROOT, Hist, build_events, geohash


def main(seed: int = 7) -> None:
    from api.app.db import SessionLocal, init_db
    from api.app.models import Report
    from api.app.schemas import ReportIn
    from api.app.service import ingest
    from sqlalchemy import func, select

    init_db()
    db = SessionLocal()
    if db.scalar(select(func.count()).select_from(Report)):
        print("이미 데이터가 있어 건너뛴다")
        return
    H = {k: Hist(v) for k, v in json.loads((ROOT / "docs/results/phash.json").read_text())["_histograms"].items()}
    rng = random.Random(seed)
    _, events = build_events(rng, 6.0, H)
    for e in events:
        crack = [] if e.width is None else [{
            "width_mm": e.width, "width_ci_mm": [max(0.0, e.width - 0.1 - 0.15 * e.width), e.width + 0.1 + 0.15 * e.width],
            "length_mm": 200.0, "orientation_deg": 60.0, "polyline": [[0.2, 0.2], [0.3, 0.8]], "confidence": 0.7}]
        payload = ReportIn(
            client_uuid=str(uuid.UUID(int=rng.getrandbits(128))), captured_at=e.captured,
            location={"lat": e.lat, "lon": e.lon, "accuracy_m": e.acc, "geohash": geohash(e.lat, e.lon)},
            calibration={"patch_found": e.card, "delta_e_after": 1.5 if e.card else None,
                         "quality": "good" if e.card else "poor"},
            detection={"engine": "demo(합성)", "cracks": crack},
            image_meta={"w": 1600, "h": 1200, "blur_score": e.blur, "exif_stripped": True},
            phash=e.phash, note=f"[합성 데모] {e.kind}",
        )
        ingest(db, payload, e.device, e.received)
    print(f"{len(events)}건 넣음")


if __name__ == "__main__":
    main()
