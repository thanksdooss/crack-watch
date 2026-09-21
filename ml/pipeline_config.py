"""shared/pipeline.json을 읽는 단일 진입점. 전처리 상수를 코드에 적지 않는다."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parents[1] / "shared" / "pipeline.json"


@lru_cache(maxsize=1)
def load() -> dict[str, Any]:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)
