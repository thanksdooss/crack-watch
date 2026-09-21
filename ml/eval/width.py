"""폭 추정 오차 — 합성 test(정답 폭을 앎)에서 세 측정법을 비교한다.

    python -m ml.eval.width

두 조건에서 잰다.
- 정답 마스크: 검출이 완벽할 때 측정법 자체의 오차
- 검출 마스크: 실제로 쓰일 조건. 기준선(고전 CV)이 낸 마스크로 잰다.

px/mm는 합성 정답값을 쓴다. 기준 카드 검출에서 오는 환산 오차는 여기 없다(4단계에서 따로).
"""

from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from ml import workers
from ml.baseline.classic import ClassicParams, detect, flatten, to_gray
from ml.color.card import ROOT
from ml.measure.width import METHODS, measure
from ml.synth import sets as synth

BINS = [(0.0, 0.3, "0.3mm 이하 (머리카락 굵기)"), (0.3, 1.0, "0.3~1mm"), (1.0, 99.0, "1mm 초과")]
MATCH_PX = 2.0


def _truth_lookup(item) -> tuple[np.ndarray, np.ndarray]:
    pts = np.concatenate(item.sample.centerline)
    w = np.concatenate(item.sample.widths_mm)
    return pts, w


def _one(i: int) -> list[tuple[str, float, dict]]:
    item = synth.get("test", i)
    if not item.has_crack:
        return []
    flat = flatten(to_gray(item.sample.image), ClassicParams.from_config().flatten_sigma)
    det_mask, _ = detect(item.sample.image)
    pts, wmm = _truth_lookup(item)
    ppm = item.sample.px_per_mm
    out = []
    for cond, mask in (("gt", item.sample.mask), ("detected", det_mask)):
        for s in measure(flat, mask):
            d = np.hypot(pts[:, 0] - s.x, pts[:, 1] - s.y)
            j = int(np.argmin(d))
            if d[j] > MATCH_PX:
                continue  # 오탐 위치의 폭은 검출 문제라 여기서 세지 않는다
            out.append((cond, float(wmm[j]), {m: getattr(s, m) / ppm for m in METHODS}))
    return out


def run() -> dict:
    with ProcessPoolExecutor(max_workers=workers()) as ex:
        rows = [r for part in ex.map(_one, range(synth.size("test"))) for r in part]
    result: dict = {}
    for cond in ("gt", "detected"):
        result[cond] = {}
        for lo, hi, label in BINS:
            sel = [(t, est) for c, t, est in rows if c == cond and lo < t <= hi]
            if not sel:
                continue
            truth = np.array([t for t, _ in sel])
            result[cond][label] = {"n": len(sel)}
            for m in METHODS:
                est = np.array([e[m] for _, e in sel])
                err = est - truth
                result[cond][label][m] = {
                    "mae_mm": float(np.mean(np.abs(err))),
                    "bias_mm": float(np.mean(err)),
                    "p90_abs_mm": float(np.percentile(np.abs(err), 90)),
                    "rel_mae": float(np.mean(np.abs(err) / truth)),
                }
    out = Path(ROOT) / "docs" / "results" / "width.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    r = run()
    for cond, bins in r.items():
        print(f"== {cond}")
        for label, v in bins.items():
            cells = "  ".join(f"{m}: MAE {v[m]['mae_mm']:.3f} bias {v[m]['bias_mm']:+.3f}" for m in METHODS)
            print(f"  {label} (n={v['n']}): {cells}")
