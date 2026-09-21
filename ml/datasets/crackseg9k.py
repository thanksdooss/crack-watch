"""CrackSeg9k 목록 만들기 — 출처 분류, 라이선스 제외, 고정 분할.

    from ml.datasets.crackseg9k import index
    rows = index()            # 학습·평가에 쓸 수 있는 것만
    rows = index(split="test")

라이선스 처리 (docs/00-approach.md 3절, docs/decisions.md):
CrackSeg9k 묶음은 CC0으로 게시되어 있지만, 원 배포처가 **비상업·등록 조건을 명시한**
하위 세트는 묶음의 CC0 선언과 관계없이 쓰지 않는다.
  - DeepCrack: 원 저장소가 "비상업 연구·교육 한정"
  - CFD(CrackForest): 원 저장소가 "비상업 연구 한정"
  - GAPs: 원 배포처가 등록과 연구 목적 동의를 요구
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ml.color.card import ROOT

BASE = Path(ROOT) / "data" / "crackseg9k"
MASK_DIR = BASE / "Final-Dataset-Vol1" / "Final_Masks" / "Masks"

# (파일명 접두어, 출처, 표면, 사용 여부, 끝에서 떼어낼 조각 좌표 개수)
# 조각 좌표 개수는 파일명 구조를 보고 정했다. 예:
#   CRACK500_20160307_164400_1281_721          → 원본 CRACK500_20160307_164400 (2개 뗌)
#   Rissbilder_for_Florian_9S6A2782_0_0_3840_5760 → 원본 ..._9S6A2782 (4개 뗌)
#   noncrack_noncrack_concrete_wall_20_71      → 원본 ..._wall_20 (1개 뗌)
SOURCES: list[tuple[str, str, str, bool, int]] = [
    ("noncrack_", "noncrack", "콘크리트 벽(균열 없음)", True, 1),
    ("Rissbilder_", "rissbilder", "건물 외벽", True, 4),
    ("Volker_", "volker", "건물 외벽", True, 4),
    ("CRACK500_", "crack500", "포장도로", True, 2),
    ("cracktree", "cracktree", "포장도로", True, 0),
    ("Ceramic_", "ceramic", "타일", True, 0),
    ("a_", "masonry", "벽돌 벽", True, 1),
    ("b_", "masonry", "벽돌 벽", True, 1),
    ("c_", "masonry", "벽돌 벽", True, 1),
    ("d_", "masonry", "벽돌 벽", True, 1),
    ("h_", "masonry", "벽돌 벽", True, 1),
    ("DeepCrack", "deepcrack", "도로·콘크리트", False, 0),
    ("CFD_", "cfd", "도로", False, 0),
    ("GAPS", "gaps", "아스팔트", False, 0),
]

# 건물 벽면 — 우리 제품이 실제로 찍힐 표면. 평가에서 따로 본다.
WALL_SOURCES = {"noncrack", "rissbilder", "volker", "masonry"}


@dataclass(frozen=True)
class Row:
    image: Path
    mask: Path
    source: str
    surface: str
    split: str


def _source(name: str) -> tuple[str, str, bool, int] | None:
    for prefix, src, surface, allowed, strip in SOURCES:
        if name.startswith(prefix):
            return src, surface, allowed, strip
    return None


def _split(name: str, strip: int) -> str:
    """원본 사진 이름의 해시로 고정 분할: train 80 / val 10 / test 10. 실행할 때마다 같다.

    한 장의 원본을 여러 조각으로 잘라 둔 출처가 많다. 조각 단위로 나누면 같은 벽의
    옆 조각이 train과 test에 갈라져 들어가, test가 train을 거의 베낀 셈이 되고 점수가
    부풀려진다. 그래서 조각 좌표를 떼어낸 원본 이름으로 나눈다.
    """
    parts = Path(name).stem.split("_")
    key = "_".join(parts[: len(parts) - strip] if strip else parts)
    h = int(hashlib.sha1(key.encode()).hexdigest(), 16) % 100
    return "train" if h < 80 else "val" if h < 90 else "test"


@lru_cache(maxsize=1)
def _all() -> tuple[Row, ...]:
    if not MASK_DIR.exists():
        raise FileNotFoundError(f"{BASE} 없음 — python -m ml.datasets.download crackseg9k")
    rows = []
    for img in sorted(BASE.glob("Final-Dataset-Vol*/Images*/*.png")):
        info = _source(img.name)
        if info is None:
            continue
        src, surface, allowed, strip = info
        if not allowed:
            continue
        mask = MASK_DIR / img.name
        if mask.exists():
            rows.append(Row(img, mask, src, surface, _split(img.name, strip)))
    return tuple(rows)


def index(split: str | None = None, sources: set[str] | None = None) -> list[Row]:
    return [r for r in _all() if (split is None or r.split == split)
            and (sources is None or r.source in sources)]


def excluded_count() -> dict[str, int]:
    out: dict[str, int] = {}
    for img in BASE.glob("Final-Dataset-Vol*/Images*/*.png"):
        info = _source(img.name)
        if info and not info[2]:
            out[info[0]] = out.get(info[0], 0) + 1
    return out
