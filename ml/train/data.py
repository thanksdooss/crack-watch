"""CrackSeg9k 학습 데이터 + 증강.

증강은 '시민이 스마트폰으로 찍는 조건'을 흉내 내는 쪽으로 고른다.
- 방향: 뒤집기·90도 회전 (균열 방향에 편향이 생기지 않게)
- 색: 채널별 이득(화이트밸런스 틀어짐), 밝기·대비·감마 (조명)
- 선명도: 가우시안 흐림, 해상도 낮췄다 올리기 (흔들림·원거리 촬영)
색 보정 단계가 앞에 있어도 완벽하지 않으므로, 모델이 남은 색 틀어짐에 둔감해야 한다.
"""

from __future__ import annotations

import cv2
import numpy as np
import torch
from torch.utils.data import Dataset

from ml.color.card import pipeline_config
from ml.datasets.crackseg9k import Row

MEAN = np.array(pipeline_config()["normalize"]["mean"], np.float32)
STD = np.array(pipeline_config()["normalize"]["std"], np.float32)


def normalize(img: np.ndarray) -> np.ndarray:
    """RGB float 0~1 (H,W,3) → 정규화된 (3,H,W). 웹 전처리와 같은 상수(shared/pipeline.json)."""
    return ((img - MEAN) / STD).transpose(2, 0, 1).astype(np.float32)


def load_pair(row: Row) -> tuple[np.ndarray, np.ndarray]:
    img = cv2.cvtColor(cv2.imread(str(row.image)), cv2.COLOR_BGR2RGB).astype(np.float32) / 255
    mask = (cv2.imread(str(row.mask), cv2.IMREAD_GRAYSCALE) > 127).astype(np.float32)
    return img, mask


def augment(img: np.ndarray, mask: np.ndarray, rng: np.random.Generator, crop: int
            ) -> tuple[np.ndarray, np.ndarray]:
    h, w = mask.shape
    if h < crop or w < crop:
        ph, pw = max(0, crop - h), max(0, crop - w)
        img = cv2.copyMakeBorder(img, 0, ph, 0, pw, cv2.BORDER_REFLECT)
        mask = cv2.copyMakeBorder(mask, 0, ph, 0, pw, cv2.BORDER_CONSTANT, value=0)
        h, w = mask.shape
    y, x = rng.integers(0, h - crop + 1), rng.integers(0, w - crop + 1)
    img, mask = img[y:y + crop, x:x + crop], mask[y:y + crop, x:x + crop]

    if rng.random() < 0.5:
        img, mask = img[:, ::-1], mask[:, ::-1]
    k = int(rng.integers(0, 4))
    img, mask = np.rot90(img, k), np.rot90(mask, k)

    img = img * rng.uniform(0.85, 1.15, 3).astype(np.float32)          # 화이트밸런스 틀어짐
    img = (img - 0.5) * rng.uniform(0.7, 1.3) + 0.5 + rng.uniform(-0.1, 0.1)  # 대비·밝기
    img = np.clip(img, 0, 1) ** rng.uniform(0.7, 1.4)                  # 감마
    if rng.random() < 0.3:
        img = cv2.GaussianBlur(np.ascontiguousarray(img), (0, 0), rng.uniform(0.5, 1.5))
    if rng.random() < 0.2:
        f = rng.uniform(0.5, 0.8)
        small = cv2.resize(np.ascontiguousarray(img), None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
        img = cv2.resize(small, (crop, crop), interpolation=cv2.INTER_LINEAR)
    if rng.random() < 0.3:
        img = img + rng.normal(0, rng.uniform(0.005, 0.03), img.shape).astype(np.float32)
    return np.clip(img, 0, 1).astype(np.float32), np.ascontiguousarray(mask)


class CrackDataset(Dataset):
    def __init__(self, rows: list[Row], train: bool, crop: int = 352, seed: int = 0):
        self.rows, self.train, self.crop, self.seed = rows, train, crop, seed
        self.epoch = 0

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, i: int):
        img, mask = load_pair(self.rows[i])
        if self.train:
            rng = np.random.default_rng([self.seed, self.epoch, i])
            img, mask = augment(img, mask, rng, self.crop)
        return torch.from_numpy(normalize(img)), torch.from_numpy(mask[None])
