"""웹 체험용 샘플 사진 3장 — 합성 벽면 + 기준 카드 + 서로 다른 조명.

    python -m ml.tools.make_samples

실제 건물 사진과 공개 데이터셋 이미지는 저장소에 넣지 않는다는 규칙 때문에 합성으로 만든다.
화면에도 '합성 샘플'로 표시한다. 정답(폭·축척)을 알기 때문에 E2E 테스트의 기대값으로도 쓴다.
cv2.imwrite는 EXIF를 쓰지 않는다(위치·기기 정보 없음).
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from ml.color.card import ROOT
from ml.color.card_raster import place
from ml.color.detect_card import CardDetection
from ml.color.simulate import CaptureConditions, capture
from ml.synth.wall import CrackSpec, WallSpec, generate

OUT = Path(ROOT) / "web" / "public" / "samples"

SAMPLES = [
    # (파일, 제목, 균열 폭 mm, 조명, 카드 px/mm, 회전, 기울기, 시드)
    # 기울기(원근)는 0으로 둔다. 카드만 기울이고 벽은 정면이면 카드로 잰 축척과 균열의 실제
    # 축척이 어긋나(처음 만든 샘플에서 2.8%) 정답이 흔들린다. 원근 보정 시험은 카드 검출 테스트가 맡는다.
    ("wall-daylight.jpg", "맑은 날 · 가는 균열", 0.35, "주광 D65", 5.0, 4.0, (0.0, 0.0), 11),
    ("wall-fluorescent.jpg", "형광등 · 중간 균열", 0.9, "형광등 F2", 4.5, -8.0, (0.0, 0.0), 22),
    ("wall-tungsten.jpg", "백열등 · 넓은 균열", 2.2, "백열등 A", 4.0, 175.0, (0.0, 0.0), 33),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    index = []
    for fname, title, width, light, ppm, rot, tilt, seed in SAMPLES:
        rng = np.random.default_rng(seed)
        wall_ppm = ppm  # 카드와 균열이 같은 벽면·같은 거리 → 같은 축척
        s = generate(rng, WallSpec(size_px=(900, 1200), px_per_mm=wall_ppm, stains=2, form_lines=1),
                     [CrackSpec(width_mm=width, branches=1, width_jitter=0.2)])
        scene, H = place(s.image, (920, 700), ppm, rot, tilt)
        lit = capture(scene.reshape(-1, 3), CaptureConditions(light, awb_strength=0.6, exposure=0.85,
                                                              flare=0.01)).reshape(scene.shape)
        bgr = (np.clip(lit, 0, 1)[..., ::-1] * 255).round().astype(np.uint8)
        cv2.imwrite(str(OUT / fname), bgr, [cv2.IMWRITE_JPEG_QUALITY, 88])
        truth = CardDetection(H, {}, 0, None)
        index.append({"file": fname, "title": title, "synthetic": True, "lighting": light,
                      "trueWidthMm": width, "truePxPerMm": round(truth.px_per_mm_at(600, 450), 4)})
    (OUT / "samples.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8")
    print(json.dumps(index, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
