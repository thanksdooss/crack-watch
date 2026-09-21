"""고전 CV 파라미터 격자 탐색 — 합성 dev + CrackSeg9k val. test는 보지 않는다.

    python -m ml.baseline.tune           # 합성 dev + 실제 val
    python -m ml.baseline.tune --synth   # 합성 dev만

목표: 허용 F1(합성·실제 평균) 최대.
조건: 균열 없는 벽에서 헛경보율이 상한 이하 — 합성 음성과 실제 noncrack 둘 다.
헛신고가 채널을 죽이므로 재현율보다 오탐 억제를 앞에 둔다.

실제 사진이 들어가는 이유: 모델은 실제 사진으로 학습한다. 기준선을 합성에서만 고르면
실제 사진에서 억울하게 낮게 나와 '모델이 X배 낫다'가 부풀려진다.
"""

from __future__ import annotations

import itertools
import json
import os
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from ml import workers
from ml.baseline import classic as C
from ml.color.card import ROOT
from ml.eval.metrics import Counts, count

# 탐색 라운드. 최적값이 격자 가장자리에 걸리면 기준선을 불리하게 둔 것이므로 범위를 넓힌다.
#  1라운드(합성 dev 전용, 528개): c=0.05·high=0.95는 상위권에 없음.
#  2라운드(합성+실제 val, 288개): 최적 c=0.35가 가장자리 → 3라운드에서 더 넓힘.
ROUNDS = {
    2: dict(scales=[(1.0, 1.5, 2.0, 3.0), (1.5, 2.0, 3.0, 4.0)], cs=[0.1, 0.2, 0.35],
            highs=[0.5, 0.7, 0.85], lows=[0.2, 0.35, 0.5], lens=[24, 48, 80], elongs=[4.0, 8.0]),
    3: dict(scales=[(1.5, 2.0, 3.0, 4.0), (2.0, 3.0, 4.0, 6.0), (1.5, 2.0, 3.0, 4.0, 6.0)],
            cs=[0.35, 0.5, 0.7, 1.0], highs=[0.3, 0.4, 0.5], lows=[0.1, 0.2],
            lens=[32, 48, 80], elongs=[8.0, 12.0]),
}
ROUND = 3
FA_LIMITS = [0.15, 0.25, 0.35, 0.5]  # 앞에서부터 만족하는 게 있으면 그걸 쓴다
REAL_CRACK_PER_SOURCE = 40
REAL_NEG = 60
SEED = 7


def grid():
    g = ROUNDS[ROUND]
    for sc, c, hi, lo, ml, me in itertools.product(g["scales"], g["cs"], g["highs"], g["lows"],
                                                   g["lens"], g["elongs"]):
        if lo < hi:
            yield dict(scales=sc, c=c, hyst_high=hi, hyst_low=lo, min_length_px=ml,
                       min_elongation=me)


def jobs(with_real: bool) -> list[tuple]:
    from ml.synth.sets import size

    out: list[tuple] = [("synth", i) for i in range(size("dev"))]
    if with_real:
        from ml.datasets.crackseg9k import index

        rng = random.Random(SEED)
        val = index(split="val")
        by_src: dict[str, list] = {}
        for r in val:
            by_src.setdefault(r.source, []).append(r)
        for src, rows in sorted(by_src.items()):
            k = REAL_NEG if src == "noncrack" else REAL_CRACK_PER_SOURCE
            for r in rng.sample(rows, min(k, len(rows))):
                out.append(("real", str(r.image), str(r.mask), src))
    return out


def _one(job):
    if job[0] == "synth":
        from ml.synth.sets import get

        item = get("dev", job[1])
        img, gt, has_crack, kind = item.sample.image, item.sample.mask, item.has_crack, "synth"
    else:
        from ml.eval.detection import read_mask, read_rgb

        img, gt = read_rgb(Path(job[1])), read_mask(Path(job[2]))
        has_crack, kind = bool(gt.any()), "real"
    base = C.ClassicParams.from_config()
    flat = C.flatten(C.to_gray(img), base.flatten_sigma)
    cache = {}
    res = []
    for g in grid():
        key = (g["scales"], g["c"])
        if key not in cache:
            cache[key] = C.ridge_response(flat, C.ClassicParams.from_config(**g))
        m = C.shape_filter(C.hysteresis(cache[key], g["hyst_low"], g["hyst_high"]),
                           g["min_length_px"], g["min_elongation"])
        res.append(count(m, gt) if has_crack else bool(m.any()))
    return kind, has_crack, res


def main() -> None:
    with_real = "--synth" not in sys.argv
    configs = list(grid())
    js = jobs(with_real)
    print(f"{len(configs)} configs × {len(js)} images", flush=True)
    with ProcessPoolExecutor(max_workers=workers()) as ex:
        results = list(ex.map(_one, js, chunksize=2))

    rows = []
    for k, cfg in enumerate(configs):
        stat = {kind: [Counts(), 0, 0] for kind in ("synth", "real")}
        for kind, has_crack, per in results:
            if has_crack:
                stat[kind][0].add(per[k])
            else:
                stat[kind][1] += int(per[k])
                stat[kind][2] += 1
        row = {**cfg}
        for kind, (c, fa, n) in stat.items():
            if c.tol_r_all == 0 and n == 0:
                continue
            row[f"{kind}_tol_f1"] = c.tol_f1
            row[f"{kind}_iou"] = c.iou
            row[f"{kind}_fa"] = fa / n if n else 0.0
        kinds = [k for k in ("synth", "real") if f"{k}_tol_f1" in row]
        row["score"] = sum(row[f"{k}_tol_f1"] for k in kinds) / len(kinds)
        row["worst_fa"] = max(row[f"{k}_fa"] for k in kinds)
        rows.append(row)

    out = Path(ROOT) / "data" / f"tune_classic_r{ROUND}{'' if with_real else '_synth'}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(rows, indent=1))

    for limit in FA_LIMITS:
        ok = sorted((r for r in rows if r["worst_fa"] <= limit), key=lambda r: -r["score"])
        if ok:
            print(f"헛경보 상한 {limit:.0%}에서 {len(ok)}개 만족. 상위:")
            for r in ok[:6]:
                print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()})
            break
    best_any = max(rows, key=lambda r: r["score"])
    print("헛경보 무시 최고:", {k: (round(v, 3) if isinstance(v, float) else v)
                            for k, v in best_any.items()})


if __name__ == "__main__":
    main()
