"""검출 평가 지표.

균열은 이미지의 1~3%밖에 안 된다. 그래서 '정확도(accuracy)'는 쓰지 않는다 — 전부
배경이라고 답해도 97%가 나온다. 대신:

- IoU: 예측과 정답이 겹친 넓이 / 합친 넓이. 엄격하다 — 1px 어긋나도 깎인다.
- 정밀도: 균열이라고 한 것 중 진짜 균열 비율 (낮으면 오탐이 많다 = 헛신고)
- 재현율: 진짜 균열 중 찾아낸 비율 (낮으면 놓친다)
- 허용 오차 버전(tol): 정답에서 2px 안이면 맞춘 것으로 친다. 폭 1~2px짜리 균열에서
  라벨 경계 자체가 ±1px 흔들리므로, 엄격 IoU만 보면 방법 간 차이가 라벨 잡음에 묻힌다.
  균열 검출 논문들도 같은 이유로 허용 오차 F1을 같이 쓴다.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

TOLERANCE_PX = 2


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tol_p_hit: int = 0  # 예측 픽셀 중 정답 근처인 것
    tol_p_all: int = 0
    tol_r_hit: int = 0  # 정답 픽셀 중 예측 근처인 것
    tol_r_all: int = 0

    def add(self, other: "Counts") -> None:
        for k in self.__dataclass_fields__:
            setattr(self, k, getattr(self, k) + getattr(other, k))

    @property
    def iou(self) -> float:
        d = self.tp + self.fp + self.fn
        return self.tp / d if d else 1.0

    @property
    def precision(self) -> float:
        d = self.tp + self.fp
        return self.tp / d if d else 1.0

    @property
    def recall(self) -> float:
        d = self.tp + self.fn
        return self.tp / d if d else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    @property
    def tol_precision(self) -> float:
        return self.tol_p_hit / self.tol_p_all if self.tol_p_all else 1.0

    @property
    def tol_recall(self) -> float:
        return self.tol_r_hit / self.tol_r_all if self.tol_r_all else 1.0

    @property
    def tol_f1(self) -> float:
        p, r = self.tol_precision, self.tol_recall
        return 2 * p * r / (p + r) if p + r else 0.0


def _near(mask: np.ndarray, tol: int) -> np.ndarray:
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * tol + 1, 2 * tol + 1))
    return cv2.dilate(mask.astype(np.uint8), k) > 0


def count(pred: np.ndarray, gt: np.ndarray, tol: int = TOLERANCE_PX) -> Counts:
    pred = pred.astype(bool)
    gt = gt.astype(bool)
    return Counts(
        tp=int(np.sum(pred & gt)),
        fp=int(np.sum(pred & ~gt)),
        fn=int(np.sum(~pred & gt)),
        tol_p_hit=int(np.sum(pred & _near(gt, tol))),
        tol_p_all=int(pred.sum()),
        tol_r_hit=int(np.sum(gt & _near(pred, tol))),
        tol_r_all=int(gt.sum()),
    )
