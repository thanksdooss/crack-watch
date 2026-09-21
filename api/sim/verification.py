"""신고 검증 시뮬레이션 — 정답을 아는 신고 흐름을 흘려 넣고, 무엇이 걸러지는지 센다.

    python -m api.sim.verification        # docs/results/verification.json

실제 신고 데이터가 없으므로 흐름을 합성한다. 다만 지각 해시 거리는 가정하지 않고
실제 벽 사진으로 잰 분포(docs/results/phash.json)에서 뽑는다.

신고 종류(정답 라벨)와 기대 결과
  정상  first / followup(같은 사람이 며칠 뒤) / corroborate(다른 사람) → 접수(pending), 같은 지점에 묶임
  중복  double_tap(같은 사람이 몇 분 뒤 재전송) / viral(같은 사진을 여러 사람이) → 병합(merged)
  나쁨  prank_junk(균열도 카드도 없는 아무 사진, 흔들린 사진) / prank_reused(남의 사진을 먼 곳에) /
        wrong_building(A 벽을 찍고 B 건물 위치로) / flood(한 기기가 한 시간에 25건) → 보류(held)
  나쁨  prank_convincing(선명하고 균열도 보이는 가짜, 카드 유무 섞임) → 정상 신고와 규칙으로
        구별할 수 없다. 걸러야 할 대상으로 세지 않고 따로 보고한다 — 사람이 봐야 하는 몫.
"""

from __future__ import annotations

import json
import math
import os
import random
import sys
import tempfile
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CENTER = (37.5665, 126.9780)  # 중립 좌표(특정 건물 아님)
BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"


def geohash(lat: float, lon: float, precision: int = 8) -> str:
    la, lo = [-90.0, 90.0], [-180.0, 180.0]
    out, bit, ch, even = "", 0, 0, True
    while len(out) < precision:
        r, v = (lo, lon) if even else (la, lat)
        mid = (r[0] + r[1]) / 2
        if v >= mid:
            ch, r[0] = (ch << 1) | 1, mid
        else:
            ch, r[1] = ch << 1, mid
        even = not even
        bit += 1
        if bit == 5:
            out, bit, ch = out + BASE32[ch], 0, 0
    return out


def offset(lat: float, lon: float, dx_m: float, dy_m: float) -> tuple[float, float]:
    return lat + dy_m / 111_320, lon + dx_m / (111_320 * math.cos(math.radians(lat)))


class Hist:
    def __init__(self, counts: list[int]):
        self.values = [d for d, c in enumerate(counts) for _ in range(c)]

    def sample(self, rng: random.Random) -> int:
        return rng.choice(self.values)


def flip(h: str, d: int, rng: random.Random) -> str:
    v = int(h, 16)
    for b in rng.sample(range(64), d):
        v ^= 1 << b
    return f"{v:016x}"


@dataclass
class Wall:
    id: int
    lat: float
    lon: float
    hash: str
    cracked: bool
    w0: float
    growth: float  # 90일 동안 늘어나는 폭(mm)


@dataclass
class Event:
    kind: str
    wall: int | None
    device: str
    captured: datetime
    received: datetime
    lat: float
    lon: float
    acc: float
    phash: str
    card: bool
    blur: float
    width: float | None


def build_events(rng: random.Random, gps_sigma: float, H: dict[str, Hist]) -> tuple[list[Wall], list[Event]]:
    t0 = datetime(2026, 6, 1, tzinfo=timezone.utc)
    walls: list[Wall] = []
    for b in range(40):
        blat, blon = offset(*CENTER, rng.uniform(-1500, 1500), rng.uniform(-1500, 1500))
        bhash = f"{rng.getrandbits(64):016x}"
        for _ in range(rng.randint(2, 4)):  # 한 건물의 벽들은 15m 안에 모여 있다 — 충돌 위험이 여기서 생긴다
            lat, lon = offset(blat, blon, rng.uniform(-8, 8), rng.uniform(-8, 8))
            walls.append(Wall(len(walls), lat, lon, flip(bhash, H["different"].sample(rng), rng),
                              False, rng.uniform(0.1, 1.2), rng.choice([0.0, 0.0, 0.0, rng.uniform(0.2, 0.6)])))
    for w in rng.sample(walls, 50):
        w.cracked = True
    cracked = [w for w in walls if w.cracked]
    citizens = [f"citizen-{i}" for i in range(150)]
    ev: list[Event] = []
    last_hash: dict[int, str] = {}

    def legit(kind: str, w: Wall, dev: str, when: datetime, base_hash: str | None = None,
              dist_key: str = "same_scene") -> Event:
        dx, dy = rng.gauss(0, gps_sigma), rng.gauss(0, gps_sigma)
        lat, lon = offset(w.lat, w.lon, dx, dy)
        acc = abs(math.hypot(dx, dy)) * 1.3 + rng.uniform(3, 10)
        if rng.random() < 0.05:
            acc = rng.uniform(60, 120)  # 실내·골목에서 GPS가 나쁨
        h = flip(base_hash or w.hash, H[dist_key].sample(rng), rng)
        day = (when - t0).days
        width = max(0.05, w.w0 + w.growth * day / 90 + rng.gauss(0, 0.08))
        return Event(kind, w.id, dev, when, when + timedelta(minutes=rng.uniform(1, 60)), lat, lon, acc, h,
                     rng.random() > 0.10, rng.uniform(0.6, 0.9) if rng.random() < 0.05 else rng.uniform(0.05, 0.4),
                     width)

    for w in cracked:
        dev = rng.choice(citizens)
        when = t0 + timedelta(days=rng.uniform(0, 45))
        first = legit("first", w, dev, when)
        ev.append(first)
        if rng.random() < 0.6:
            ev.append(legit("followup", w, dev, when + timedelta(days=rng.uniform(7, 40)), first.phash))
        if rng.random() < 0.5:
            ev.append(legit("corroborate", w, rng.choice([c for c in citizens if c != dev]),
                            when + timedelta(hours=rng.uniform(3, 480)), first.phash))
        if rng.random() < 0.5:
            e = legit("double_tap", w, dev, when + timedelta(minutes=rng.uniform(1, 10)), first.phash, "same_photo")
            ev.append(e)
        if rng.random() < 0.25:
            e = legit("viral", w, rng.choice(citizens), when + timedelta(minutes=rng.uniform(5, 90)), first.phash,
                      "same_photo")
            ev.append(e)
        last_hash[w.id] = first.phash

    def random_spot() -> tuple[float, float]:
        return offset(*CENTER, rng.uniform(-3000, 3000), rng.uniform(-3000, 3000))

    for i in range(20):  # 쓰레기 사진: 주머니 속·하늘·셀카 — 균열이 안 잡히고 카드도 없다
        lat, lon = random_spot()
        when = t0 + timedelta(days=rng.uniform(0, 90))
        ev.append(Event("prank_junk", None, f"prank-{i % 5}", when, when + timedelta(minutes=5), lat, lon,
                        rng.uniform(5, 30), f"{rng.getrandbits(64):016x}", False,
                        rng.uniform(0.65, 0.95) if rng.random() < 0.5 else rng.uniform(0.1, 0.4),
                        None if rng.random() < 0.8 else rng.uniform(0.2, 3)))
    for i in range(10):
        lat, lon = random_spot()
        when = t0 + timedelta(days=rng.uniform(0, 90))
        ev.append(Event("prank_convincing", None, f"faker-{i}", when, when + timedelta(minutes=5), lat, lon,
                        rng.uniform(5, 20), f"{rng.getrandbits(64):016x}", rng.random() < 0.5, rng.uniform(0.1, 0.4),
                        rng.uniform(0.3, 2)))
    firsts = [e for e in ev if e.kind == "first"]
    for i in range(15):
        src = rng.choice(firsts)
        lat, lon = offset(src.lat, src.lon, rng.choice([-1, 1]) * rng.uniform(1000, 8000), rng.uniform(-3000, 3000))
        when = src.received + timedelta(days=rng.uniform(1, 30))
        ev.append(Event("prank_reused", None, f"prank-{i % 5}", when, when + timedelta(minutes=3), lat, lon,
                        rng.uniform(5, 20), flip(src.phash, H["same_photo"].sample(rng), rng), src.card, src.blur,
                        src.width))
    for i in range(15):
        w = rng.choice(cracked)
        e = legit("wrong_building", w, rng.choice(citizens), t0 + timedelta(days=rng.uniform(50, 90)), last_hash[w.id])
        ang = rng.uniform(0, 2 * math.pi)
        dist = rng.uniform(40, 300)
        e.lat, e.lon = offset(w.lat, w.lon, dist * math.cos(ang), dist * math.sin(ang))
        e.wall = None
        ev.append(e)
    start = t0 + timedelta(days=rng.uniform(10, 80))
    for i in range(25):
        lat, lon = random_spot()
        when = start + timedelta(minutes=i * 2.3)
        ev.append(Event("flood", None, "flooder", when, when + timedelta(seconds=30), lat, lon, 10.0,
                        f"{rng.getrandbits(64):016x}", True, 0.2, rng.uniform(0.2, 1.0)))
    ev.sort(key=lambda e: e.received)
    return walls, ev


GROUP = {"first": "정상", "followup": "정상", "corroborate": "정상", "double_tap": "중복", "viral": "중복",
         "prank_junk": "나쁨", "prank_reused": "나쁨", "wrong_building": "나쁨", "flood": "나쁨",
         "prank_convincing": "나쁨(규칙 밖)"}


def run(seed: int, gps_sigma: float, H: dict[str, Hist]) -> dict:
    tmp = tempfile.mkdtemp()
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp}/sim.db"
    for m in [k for k in sys.modules if k.startswith("api.app")]:
        del sys.modules[m]
    from api.app.db import SessionLocal, init_db
    from api.app.schemas import ReportIn
    from api.app.service import ingest
    from sqlalchemy import select

    init_db()
    rng = random.Random(seed)
    walls, events = build_events(rng, gps_sigma, H)
    db = SessionLocal()
    ids = []
    for e in events:
        crack = [] if e.width is None else [{
            "width_mm": e.width, "width_ci_mm": [max(0.0, e.width - 0.1 - 0.15 * e.width), e.width + 0.1 + 0.15 * e.width],
            "length_mm": 200.0, "orientation_deg": 60.0, "polyline": [[0.2, 0.2], [0.3, 0.8]], "confidence": 0.7}]
        payload = ReportIn(
            client_uuid=str(uuid.UUID(int=rng.getrandbits(128))), captured_at=e.captured,
            location={"lat": e.lat, "lon": e.lon, "accuracy_m": e.acc, "geohash": geohash(e.lat, e.lon)},
            calibration={"patch_found": e.card, "delta_e_after": 1.5 if e.card else None,
                         "quality": "good" if e.card else "poor"},
            detection={"engine": "sim", "cracks": crack},
            image_meta={"w": 1600, "h": 1200, "blur_score": e.blur, "exif_stripped": True},
            phash=e.phash,
        )
        ids.append(ingest(db, payload, e.device, e.received).id)

    # 최종 상태로 센다(도배 소급 보류처럼 접수 뒤에 바뀌는 상태가 있다)
    from api.app.models import Report
    final = {r.id: r for r in db.scalars(select(Report))}
    ev_of = {rid: e for rid, e in zip(ids, events)}
    outcomes = [(e, final[rid]) for rid, e in zip(ids, events)]
    db.close()

    by_kind: dict[str, Counter] = defaultdict(Counter)
    for e, r in outcomes:
        by_kind[e.kind][r.state] += 1

    # 같은 사진 묶음(first + double_tap + viral, 같은 벽): 하나만 남고 나머지가 그 묶음 안으로
    # 병합되면 맞다. 재전송이 원본보다 먼저 도착해 원본이 병합되는 경우도 맞은 처리로 본다.
    DUP_GROUP = ("first", "double_tap", "viral")
    dup_expected = sum(1 for e, _ in outcomes if e.kind in ("double_tap", "viral"))
    dup_caught = 0
    legit_wrong_merge = 0
    for e, r in outcomes:
        if r.state != "merged":
            continue
        src = ev_of.get(r.duplicate_of)
        same_group = src is not None and src.wall == e.wall and src.kind in DUP_GROUP and e.kind in DUP_GROUP
        if same_group:
            dup_caught += 1
        elif e.kind in ("first", "followup", "corroborate"):
            legit_wrong_merge += 1

    # 지점 연결: 같은 벽의 정상 신고들이 한 지점으로 모였는가
    site_of_wall: dict[int, Counter] = defaultdict(Counter)
    for e, r in outcomes:
        if e.kind in ("first", "followup", "corroborate") and r.site_id:
            site_of_wall[e.wall][r.site_id] += 1
    main_site = {w: c.most_common(1)[0][0] for w, c in site_of_wall.items()}
    link_ok = link_all = 0
    for e, r in outcomes:
        if e.kind in ("followup", "corroborate") and r.state == "pending":
            link_all += 1
            link_ok += int(r.site_id == main_site.get(e.wall))
    wall_of_site: dict[int, set] = defaultdict(set)
    for e, r in outcomes:
        if e.kind in ("first", "followup", "corroborate") and r.site_id:
            wall_of_site[r.site_id].add(e.wall)
    mixed_sites = sum(1 for ws in wall_of_site.values() if len(ws) > 1)

    def rate(kinds: tuple[str, ...], states: tuple[str, ...]) -> float:
        tot = sum(sum(by_kind[k].values()) for k in kinds)
        hit = sum(by_kind[k][s] for k in kinds for s in states)
        return hit / tot if tot else float("nan")

    legit = ("first", "followup", "corroborate")
    bad = ("prank_junk", "prank_reused", "wrong_building", "flood")
    n_legit = sum(sum(by_kind[k].values()) for k in legit)
    return {
        "gps_sigma_m": gps_sigma,
        "n_events": len(events),
        "by_kind": {k: dict(v) for k, v in sorted(by_kind.items())},
        "bad_held_rate": rate(bad, ("held",)),
        "bad_filtered_rate": rate(bad, ("held", "merged")),
        "convincing_prank_held_rate": rate(("prank_convincing",), ("held",)),
        "duplicate_merged_rate": dup_caught / dup_expected if dup_expected else float("nan"),
        "legit_wrongly_held_rate": rate(legit, ("held",)),
        "legit_wrongly_merged_rate": legit_wrong_merge / n_legit,
        "followup_link_rate": link_ok / link_all if link_all else float("nan"),
        "mixed_sites": float(mixed_sites),
        "per_kind_held": {k: rate((k,), ("held",)) for k in bad + ("prank_convincing",)},
    }


def main() -> None:
    H = {k: Hist(v) for k, v in json.loads((ROOT / "docs/results/phash.json").read_text())["_histograms"].items()}
    results = []
    for sigma in (3.0, 6.0, 12.0, 25.0):
        runs = [run(seed, sigma, H) for seed in range(5)]
        keys = [k for k, v in runs[0].items() if isinstance(v, float) and k != "gps_sigma_m"]
        per_kind = {k: sum(r["per_kind_held"][k] for r in runs) / len(runs) for k in runs[0]["per_kind_held"]}
        mean = {k: sum(r[k] for r in runs) / len(runs) for k in keys}
        results.append({"gps_sigma_m": sigma, "seeds": 5, **mean, "per_kind_held": per_kind, "example": runs[0]})
        print(f"GPS σ={sigma:>4}m  " + "  ".join(f"{k}={mean[k]:.3f}" for k in keys))
        print("            보류율(종류별) " + "  ".join(f"{k}={v:.2f}" for k, v in per_kind.items()))
    out = ROOT / "docs" / "results" / "verification.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
