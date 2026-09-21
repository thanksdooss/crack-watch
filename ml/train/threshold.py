"""모델 임계값·최소 면적 고르기 — val에서만.

    python -m ml.train.threshold --engine model-int8

모델은 픽셀마다 '균열일 확률'을 낸다. 몇 이상을 균열로 볼지(임계값), 몇 픽셀 미만의
조각은 버릴지(최소 면적)를 정해야 한다. 기준선과 같은 원칙으로 고른다:
허용 F1 최대, 단 균열 없는 벽(noncrack val) 헛경보율이 상한 이하.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from ml import workers
from ml.color.card import ROOT
from ml.datasets.crackseg9k import index
from ml.eval.metrics import Counts, count
from ml.train.data import load_pair
from ml.train.infer import postprocess, probability

THRESHOLDS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
MIN_AREAS = [0, 30, 80, 150, 300]
FA_LIMIT = 0.10


def _one(args):
    engine, img_path, mask_path = args
    from ml.datasets.crackseg9k import Row

    img, gt = load_pair(Row(Path(img_path), Path(mask_path), "", "", ""))
    prob = probability(engine, img)
    res = []
    for t, a in itertools.product(THRESHOLDS, MIN_AREAS):
        m = postprocess(prob, t, a)
        res.append(count(m, gt) if gt.any() else bool(m.any()))
    return bool(gt.any()), res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="model-int8")
    engine = ap.parse_args().engine
    rows = index(split="val")
    with ProcessPoolExecutor(max_workers=workers()) as ex:
        results = list(ex.map(_one, [(engine, str(r.image), str(r.mask)) for r in rows], chunksize=8))
    table = []
    for k, (t, a) in enumerate(itertools.product(THRESHOLDS, MIN_AREAS)):
        tot, fa, neg = Counts(), 0, 0
        for has, res in results:
            if has:
                tot.add(res[k])
            else:
                neg += 1
                fa += int(res[k])
        table.append({"threshold": t, "min_area": a, "tol_f1": tot.tol_f1, "iou": tot.iou,
                      "fa": fa / max(neg, 1)})
    ok = [r for r in table if r["fa"] <= FA_LIMIT] or table
    best = max(ok, key=lambda r: r["tol_f1"])
    for r in sorted(table, key=lambda r: -r["tol_f1"])[:8]:
        print({k: round(v, 3) if isinstance(v, float) else v for k, v in r.items()})
    print("선택:", best)

    p = Path(ROOT) / "shared" / "pipeline.json"
    cfg = json.loads(p.read_text(encoding="utf-8"))
    cfg.setdefault("model", {}).update({
        "$comment": f"임계값·최소 면적은 val에서 고름(헛경보 상한 {FA_LIMIT:.0%}). ml.train.threshold",
        "threshold": best["threshold"],
        "minArea": best["min_area"],
    })
    p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
