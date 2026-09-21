"""웹(TS) 구현이 파이썬과 같은 답을 내는지 검사할 골든 데이터를 만든다.

    python -m ml.tools.make_fixtures

shared/fixtures/golden/에 원시 바이너리(리틀엔디언)와 메타 JSON을 쓴다. PNG가 아닌 이유:
테스트 쪽에 디코더 의존성을 두지 않고, 실수값을 손실 없이 넘기려고.

입력은 합성 벽면(우리가 만든 이미지)이라 저장소에 넣어도 라이선스 문제가 없다.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from ml.baseline import classic as C
from ml.color.card import FIXTURES
from ml.measure.skeleton import thin
from ml.synth.wall import CrackSpec, WallSpec, generate
from ml.train.data import normalize

OUT = FIXTURES / "golden"


def _w(name: str, arr: np.ndarray) -> str:
    arr = np.ascontiguousarray(arr)
    (OUT / name).write_bytes(arr.astype(arr.dtype.newbyteorder("<")).tobytes())
    return name


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(424242)
    s = generate(rng, WallSpec(size_px=(192, 192), px_per_mm=8, stains=1, form_lines=1, pores=60),
                 [CrackSpec(width_mm=0.6, branches=1)])
    g = C.to_gray(s.image)
    p = C.ClassicParams.from_config()
    flat = C.flatten(g, p.flatten_sigma)
    resp = C.ridge_response(flat, p)
    mask = C.shape_filter(C.hysteresis(resp, p.hyst_low, p.hyst_high), p.min_length_px,
                          p.min_elongation)
    skel = thin(s.mask)

    rgb_small = (s.image[:32, :32] * 255).round().astype(np.uint8)
    norm = normalize(rgb_small.astype(np.float32) / 255)

    meta = {
        "w": 192, "h": 192,
        "params": {"flattenSigma": p.flatten_sigma, "scales": list(p.scales), "beta": p.beta,
                   "c": p.c, "hystHigh": p.hyst_high, "hystLow": p.hyst_low,
                   "minLengthPx": p.min_length_px, "minElongation": p.min_elongation},
        "files": {
            "gray": _w("gray.f32", g.astype(np.float32)),
            "flat": _w("flat.f32", flat.astype(np.float32)),
            "response": _w("response.f32", resp.astype(np.float32)),
            "mask": _w("mask.u8", mask.astype(np.uint8)),
            "gtMask": _w("gt_mask.u8", s.mask.astype(np.uint8)),
            "skeleton": _w("skeleton.u8", skel.astype(np.uint8)),
            "rgb32": _w("rgb32.u8", rgb_small),
            "norm32": _w("norm32.f32", norm.astype(np.float32)),
        },
        "stats": {"maskPixels": int(mask.sum()), "skeletonPixels": int(skel.sum())},
    }
    # 기준 카드가 붙은 장면 — 웹 카드 검출기 시험용. 정답 px/mm와 장면 좌표를 함께 남긴다.
    from ml.color.card_raster import place
    from ml.color.detect_card import CardDetection
    from ml.color.card import CARD_W, CARD_H, FIDUCIAL_CENTERS_MM
    card_scenes = []
    for k, (rot, tilt, ppm) in enumerate([(12.0, (0.6, -0.4), 3.2), (-150.0, (-0.9, 0.7), 2.6)]):
        rng2 = np.random.default_rng(900 + k)
        wall = generate(rng2, WallSpec(size_px=(300, 400), px_per_mm=6, stains=1), [CrackSpec(width_mm=0.8)])
        # 카드(90×56mm)가 장면 안에 온전히 들어오도록 px/mm를 작게 잡는다. 처음엔 5.5로 잡아
        # 카드가 495px — 400px 장면 밖으로 나가 있었다(검출기가 아니라 시험지가 틀렸던 경우).
        scene, H = place(wall.image, (210, 150), ppm, rot, tilt)
        corners = cv2.perspectiveTransform(np.array([[[0, 0], [CARD_W, 0], [CARD_W, CARD_H], [0, CARD_H]]],
                                                    np.float64), H)[0]
        assert corners.min() >= 0 and corners[:, 0].max() < 400 and corners[:, 1].max() < 300
        name = _w(f"card_scene_{k}.u8", (np.clip(scene, 0, 1) * 255).round().astype(np.uint8))
        truth = CardDetection(H, {}, 0, None)
        card_scenes.append({"file": name, "w": 400, "h": 300, "probe": [210, 150],
                            "pxPerMm": truth.px_per_mm_at(210, 150), "H": H.ravel().tolist()})
    meta["cardScenes"] = card_scenes

    # 폭 측정: 정답 마스크 + 평탄화 영상 → 중심선 위 표본들
    from ml.measure.width import measure
    ws = measure(flat, s.mask)
    meta["width"] = {"n": len(ws), "samples": [[w_.x, w_.y, w_.fwhm, w_.area, w_.depth, w_.hybrid] for w_ in ws],
                     "trueWidthPx": 0.6 * 8}

    # 색 보정: 백열등 아래에서 찍힌 색 칸 → 파이썬이 구한 보정 계수와 보정 후 잔차
    from ml.color import calibrate
    from ml.color.card import swatches, target_srgb
    from ml.color.simulate import CaptureConditions, capture
    names = [s_.name for s_ in swatches()]
    obs = capture(target_srgb(names), CaptureConditions("백열등 A", awb_strength=0.6, exposure=0.7, flare=0.02))
    corr = calibrate.fit(obs, names)
    meta["calibration"] = {"names": names, "observed": obs.tolist(), "gain": corr.gain.tolist(),
                           "offset": corr.offset.tolist(), "residual": corr.residual_delta_e,
                           "quality": corr.quality, "corrected": corr.apply_srgb(obs).tolist()}
    meta["card"] = {"w": CARD_W, "h": CARD_H, "fiducialCentersMm": [list(c) for c in FIDUCIAL_CENTERS_MM]}

    from ml.measure.phash import phash
    meta["phash"] = {"gray": meta["files"]["gray"], "w": 192, "h": 192, "hash": phash(g)}

    (OUT / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta["stats"]), "→", OUT)


if __name__ == "__main__":
    main()
