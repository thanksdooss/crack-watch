"""지각 해시 임계값 정하기 — '같은 장면'과 '다른 벽'의 해밍 거리 분포를 잰다.

    python -m ml.eval.phash_study      # docs/results/phash.json

같은 장면: 실제 벽 사진 한 장에 재촬영을 흉내 낸 변화를 준다 — 조명(색순응 모델), 노출,
  구도(이동 ±6%, 회전 ±6°, 확대 ±10%), 흐림, JPEG 재압축. 진짜 재촬영이 아니라는 한계가 있다.
다른 벽: 서로 다른 원본 사진끼리. 특히 민무늬 콘크리트 벽(noncrack)끼리는 모습이 비슷해서
  해시가 우연히 가까울 수 있다 — 그러면 다른 벽이 한 지점으로 묶인다(충돌).

임계값 t에 대해: 같은 장면이 t 이하로 나올 확률(묶기 재현율) vs 다른 벽이 t 이하로 나올
확률(충돌률)을 표로 남긴다.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import cv2
import numpy as np

from ml.color.card import ROOT
from ml.color.simulate import ILLUMINANTS_XY, CaptureConditions, capture
from ml.datasets import crackseg9k as cs
from ml.measure.phash import hamming, phash

SEED = 5
PER_SOURCE = 60
VARIANTS = 5
CROP = 0.85


def lum(img: np.ndarray) -> np.ndarray:
    return img[..., 0] * 0.2126 + img[..., 1] * 0.7152 + img[..., 2] * 0.0722


def reshoot(img: np.ndarray, rng: np.random.Generator, geometric: bool = True) -> np.ndarray:
    h, w = img.shape[:2]
    out = img
    if geometric:
        ang = rng.uniform(-6, 6)
        sc = rng.uniform(0.9, 1.1)
        tx, ty = rng.uniform(-0.06, 0.06) * w, rng.uniform(-0.06, 0.06) * h
        M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, sc)
        M[:, 2] += (tx, ty)
        out = cv2.warpAffine(out, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    ill = rng.choice(list(ILLUMINANTS_XY))
    cond = CaptureConditions(str(ill), awb_strength=float(rng.uniform(0.5, 0.95)),
                             exposure=float(rng.uniform(0.7, 1.15)), flare=float(rng.uniform(0, 0.03)))
    out = capture(out.reshape(-1, 3), cond).reshape(out.shape).astype(np.float32)
    if rng.random() < 0.5:
        out = cv2.GaussianBlur(out, (0, 0), float(rng.uniform(0.5, 1.5)))
    q = int(rng.integers(70, 96))
    ok, buf = cv2.imencode(".jpg", (np.clip(out, 0, 1) * 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, q])
    return cv2.imdecode(buf, cv2.IMREAD_UNCHANGED).astype(np.float32) / 255


def centre(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    dh, dw = int(h * (1 - CROP) / 2), int(w * (1 - CROP) / 2)
    return img[dh:h - dh, dw:w - dw]


def main() -> None:
    rng = np.random.default_rng(SEED)
    pick = random.Random(SEED)
    groups = {"건물 외벽": {"rissbilder", "volker"}, "벽돌 벽": {"masonry"},
              "민무늬 콘크리트(균열 없음)": {"noncrack"}}
    result = {"same_scene": {}, "same_photo": {}, "different": {}}
    for label, srcs in groups.items():
        rows = [r for split in ("val", "test") for r in cs.index(split=split, sources=srcs)]
        rows = pick.sample(rows, min(PER_SOURCE, len(rows)))
        hashes, same, same_photo = [], [], []
        for r in rows:
            img = cv2.cvtColor(cv2.imread(str(r.image)), cv2.COLOR_BGR2RGB).astype(np.float32) / 255
            base = phash(lum(centre(img)))
            hashes.append(base)
            vs = [phash(lum(centre(reshoot(img, rng)))) for _ in range(VARIANTS)]
            same += [hamming(base, v) for v in vs]
            # 같은 파일을 다시 보냄(재압축·밝기만 다름, 구도 동일) — 중복 판정용
            same_photo.append(hamming(base, phash(lum(centre(reshoot(img, rng, geometric=False))))))
        diff = [hamming(hashes[i], hashes[j]) for i in range(len(hashes)) for j in range(i + 1, len(hashes))]
        result["same_scene"][label] = same
        result["same_photo"][label] = same_photo
        result["different"][label] = diff

    summary = {}
    for label in groups:
        s = np.array(result["same_scene"][label])
        p = np.array(result["same_photo"][label])
        d = np.array(result["different"][label])
        summary[label] = {
            "n_same": len(s), "n_diff": len(d),
            "same_p50": float(np.median(s)), "same_p90": float(np.percentile(s, 90)),
            "photo_p50": float(np.median(p)), "photo_p90": float(np.percentile(p, 90)),
            "diff_p1": float(np.percentile(d, 1)), "diff_p5": float(np.percentile(d, 5)),
            "diff_p50": float(np.median(d)),
            "by_threshold": {t: {"link_recall": float(np.mean(s <= t)), "dup_recall": float(np.mean(p <= t)),
                                 "collision": float(np.mean(d <= t))} for t in range(4, 25, 2)},
        }
    # 시뮬레이션(api/sim.py)이 이 분포에서 거리를 뽑는다 — 모든 벽 종류를 합친 히스토그램
    def hist(key: str) -> list[int]:
        allv = np.concatenate([np.array(result[key][g]) for g in groups])
        return np.bincount(allv, minlength=65).tolist()
    summary["_histograms"] = {"same_scene": hist("same_scene"), "same_photo": hist("same_photo"),
                              "different": hist("different")}
    out = Path(ROOT) / "docs" / "results" / "phash.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for label, v in summary.items():
        if label.startswith("_"):
            continue
        print(label, {k: v[k] for k in ("same_p50", "same_p90", "photo_p50", "photo_p90", "diff_p1", "diff_p5", "diff_p50")})
        for t in (6, 8, 10, 12, 14, 16, 18, 20):
            b = v["by_threshold"][t]
            print(f"   t={t:2d} link {b['link_recall']:.2f} dup {b['dup_recall']:.2f} collision {b['collision']:.4f}")


if __name__ == "__main__":
    main()
