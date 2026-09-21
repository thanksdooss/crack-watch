"""ONNX 모델로 추론 — 평가도 배포할 파일 그대로 돌린다(파이토치 체크포인트가 아니라).

브라우저는 ONNX Runtime Web으로 같은 .onnx를 돌린다. 평가를 파이토치로 하면
'변환·양자화에서 잃은 성능'이 숫자에 안 잡힌다.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from ml.color.card import ROOT, pipeline_config
from ml.train.data import normalize

MODEL_DIR = Path(ROOT) / "data" / "models"
FILES = {"model-fp32": "crack_unet_fp32.onnx", "model-int8": "crack_unet_int8.onnx"}


@lru_cache(maxsize=4)
def session(name: str):
    import onnxruntime as ort

    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 1  # 평가는 프로세스 여러 개로 병렬화하므로 각자 1스레드
    opts.inter_op_num_threads = 1
    return ort.InferenceSession(str(MODEL_DIR / FILES[name]), opts,
                                providers=["CPUExecutionProvider"])


def probability(name: str, img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    ph, pw = (32 - h % 32) % 32, (32 - w % 32) % 32
    x = cv2.copyMakeBorder(img, 0, ph, 0, pw, cv2.BORDER_REFLECT)
    x = normalize(x)[None]
    sess = session(name)
    logits = sess.run(None, {sess.get_inputs()[0].name: x})[0][0, 0, :h, :w]
    return 1 / (1 + np.exp(-logits))


def postprocess(prob: np.ndarray, threshold: float, min_area: int) -> np.ndarray:
    mask = (prob >= threshold).astype(np.uint8)
    if min_area <= 0:
        return mask
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    keep = stats[:, cv2.CC_STAT_AREA] >= min_area
    keep[0] = False
    return keep[labels].astype(np.uint8)


def load(name: str):
    cfg = pipeline_config().get("model", {"threshold": 0.5, "minArea": 0})

    def detect(img: np.ndarray) -> np.ndarray:
        return postprocess(probability(name, img), cfg["threshold"], cfg["minArea"])

    return detect
