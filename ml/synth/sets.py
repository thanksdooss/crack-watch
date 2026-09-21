"""합성 평가셋 — dev(파라미터 조정용)와 test(보고용)를 시드로 나눈다.

규칙: 파라미터는 dev에서만 고른다. test 점수를 보고 파라미터를 바꾸면 test가 dev가 되고,
보고하는 숫자가 부풀려진다.

음성 샘플(균열 없는 벽)을 일부러 넣는다. 제품에서 가장 비싼 실수는 멀쩡한 벽을
균열이라고 하는 것(헛신고)이고, 그건 균열 있는 사진만으로는 측정되지 않는다.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np

from .wall import CrackSpec, Sample, WallSpec, generate

SPLITS = {"dev": (1000, 50, 15), "test": (2000, 50, 15)}  # 시드, 양성 수, 음성 수


@dataclass
class Item:
    id: str
    sample: Sample
    has_crack: bool
    width_mm: float | None


def size(split: str) -> int:
    _, n_pos, n_neg = SPLITS[split]
    return n_pos + n_neg


def iterate(split: str) -> Iterator[Item]:
    for i in range(size(split)):
        yield get(split, i)


def get(split: str, i: int) -> Item:
    """샘플마다 난수 생성기를 따로 둬서, 앞 샘플을 만들지 않고도 i번째를 바로 꺼낸다."""
    seed, n_pos, _ = SPLITS[split]
    rng = np.random.default_rng([seed, i])
    wall = WallSpec(
        px_per_mm=float(rng.uniform(5, 12)),
        texture=float(rng.uniform(0.04, 0.09)),
        pores=int(rng.integers(150, 600)),
        stains=int(rng.integers(0, 6)),
        form_lines=int(rng.integers(0, 4)),
        shadow=float(rng.uniform(0.0, 0.4)),
        blur_sigma=float(rng.uniform(0.5, 1.4)),
    )
    if i < n_pos:
        width = float(np.exp(rng.uniform(np.log(0.2), np.log(3.0))))
        crack = CrackSpec(width_mm=width, branches=int(rng.integers(0, 3)),
                          tortuosity=float(rng.uniform(0.2, 0.5)),
                          depth=float(rng.uniform(0.35, 0.65)))
        return Item(f"{split}-{i:03d}", generate(rng, wall, [crack]), True, width)
    return Item(f"{split}-{i:03d}", generate(rng, wall, []), False, None)
