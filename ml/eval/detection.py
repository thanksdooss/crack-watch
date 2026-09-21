"""검출기 평가 — 기준선과 모델을 같은 잣대로.

    python -m ml.eval.detection classic      # docs/results/classic.json 갱신
    python -m ml.eval.detection render       # docs/evaluation.md 다시 쓰기

평가 세트:
- 합성 test: 정답 폭(mm)까지 아는 세트. 음성(균열 없는 벽) 포함.
- CrackSeg9k test: 실제 사진. 출처별로 따로, 그리고 '건물 벽면'만 묶어서도 본다.
  noncrack(균열 없는 콘크리트 벽)으로 헛경보율을 잰다.

test 분할은 여기서만 쓴다. 파라미터 조정(ml.baseline.tune)은 dev/val만 본다.
"""

from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np

from ml import workers
from ml.color.card import ROOT
from ml.datasets import crackseg9k as cs
from ml.eval.metrics import Counts, count
from ml.synth import sets as synth

RESULTS = Path(ROOT) / "docs" / "results"
Detector = Callable[[np.ndarray], np.ndarray]  # RGB float 0~1 → mask 0/1


def load_detector(name: str) -> Detector:
    if name == "classic":
        from ml.baseline.classic import detect

        return lambda img: detect(img)[0]
    if name.startswith("model"):
        from ml.train.infer import load  # 3단계 모델

        return load(name)
    raise SystemExit(f"알 수 없는 검출기: {name}")


def read_rgb(path: Path) -> np.ndarray:
    return cv2.cvtColor(cv2.imread(str(path)), cv2.COLOR_BGR2RGB).astype(np.float32) / 255


def read_mask(path: Path) -> np.ndarray:
    return (cv2.imread(str(path), cv2.IMREAD_GRAYSCALE) > 127).astype(np.uint8)


def _eval_synth(args):
    name, i = args
    det = load_detector(name)
    item = synth.get("test", i)
    t = time.perf_counter()
    m = det(item.sample.image)
    dt = time.perf_counter() - t
    return item.has_crack, count(m, item.sample.mask) if item.has_crack else bool(m.any()), dt


def _eval_real(args):
    name, img_path, mask_path, source = args
    det = load_detector(name)
    img, gt = read_rgb(Path(img_path)), read_mask(Path(mask_path))
    t = time.perf_counter()
    m = det(img)
    dt = time.perf_counter() - t
    has_crack = bool(gt.any())
    return source, has_crack, count(m, gt), bool(m.any()), dt


def _summary(c: Counts) -> dict:
    return {"iou": c.iou, "precision": c.precision, "recall": c.recall, "f1": c.f1,
            "tol_precision": c.tol_precision, "tol_recall": c.tol_recall, "tol_f1": c.tol_f1}


def evaluate(name: str, n_workers: int | None = None) -> dict:
    n_workers = n_workers or workers()
    out: dict = {"engine": name}
    with ProcessPoolExecutor(max_workers=n_workers) as ex:
        res = list(ex.map(_eval_synth, [(name, i) for i in range(synth.size("test"))]))
    tot, fa, neg, times = Counts(), 0, 0, []
    for has_crack, r, dt in res:
        times.append(dt)
        if has_crack:
            tot.add(r)
        else:
            neg += 1
            fa += int(r)
    out["synth"] = {**_summary(tot), "false_alarm": fa / neg, "n_neg": neg,
                    "n_pos": len(res) - neg, "ms_per_image": 1000 * float(np.median(times))}

    rows = cs.index(split="test")
    with ProcessPoolExecutor(max_workers=n_workers) as ex:
        res = list(ex.map(_eval_real, [(name, str(r.image), str(r.mask), r.source) for r in rows],
                          chunksize=8))
    per: dict[str, Counts] = defaultdict(Counts)
    wall = Counts()
    fa_src: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    times = []
    for source, has_crack, c, any_pred, dt in res:
        times.append(dt)
        if has_crack:
            per[source].add(c)
            if source in cs.WALL_SOURCES:
                wall.add(c)
        else:
            fa_src[source][0] += int(any_pred)
            fa_src[source][1] += 1
    out["crackseg9k"] = {
        "per_source": {s: {**_summary(c), "n": sum(1 for r in rows if r.source == s)}
                       for s, c in sorted(per.items())},
        "wall": _summary(wall),
        "false_alarm": {s: {"hits": v[0], "n": v[1], "rate": v[0] / v[1]}
                        for s, v in sorted(fa_src.items())},
        "n_images": len(rows),
        "ms_per_image": 1000 * float(np.median(times)),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{name}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8")
    return out


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "classic"
    if cmd == "render":
        from ml.eval.render import render

        render()
    else:
        print(json.dumps(evaluate(cmd), ensure_ascii=False, indent=1)[:3000])
