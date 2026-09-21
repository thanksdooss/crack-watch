"""공개 데이터셋을 원 배포처에서 내려받는다. 이미지는 저장소에 들어가지 않는다(data/는 gitignore).

    python -m ml.datasets.download crackseg9k

라이선스와 선택 근거는 docs/00-approach.md 3절.
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

from ml.color.card import ROOT

DATA = Path(ROOT) / "data"
# Dataverse는 파이썬 기본 User-Agent("Python-urllib")를 403으로 막는다.
HEADERS = {"User-Agent": "crack-watch-dataset-fetcher/0.1 (research; non-commercial)"}

DATASETS = {
    "crackseg9k": {
        "license": "CC0 1.0",
        "citation": "Kulkarni et al., CrackSeg9k (ECCV Workshops 2022), doi:10.7910/DVN/EGIEBY",
        "dataverse": "https://dataverse.harvard.edu",
        "doi": "doi:10.7910/DVN/EGIEBY",
    },
}


def _dataverse_files(base: str, doi: str) -> list[dict]:
    url = f"{base}/api/datasets/:persistentId/versions/:latest/files?persistentId={doi}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as r:
        return [f["dataFile"] for f in json.load(r)["data"]]


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(url: str, dest: Path, size: int) -> None:
    """이어받기를 지원한다. 1.5GB짜리가 중간에 끊겨도 처음부터 받지 않는다."""
    have = dest.stat().st_size if dest.exists() else 0
    if have == size:
        return
    headers = {**HEADERS, **({"Range": f"bytes={have}-"} if have else {})}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as r, dest.open("ab" if have else "wb") as f:
        done = have
        while chunk := r.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            if done % (100 << 20) < (1 << 20):
                print(f"  {dest.name}: {done/1e6:.0f}/{size/1e6:.0f} MB", flush=True)


def fetch(name: str) -> Path:
    meta = DATASETS[name]
    out = DATA / name
    raw = out / "_raw"
    raw.mkdir(parents=True, exist_ok=True)
    for df in _dataverse_files(meta["dataverse"], meta["doi"]):
        dest = raw / df["filename"]
        url = f"{meta['dataverse']}/api/access/datafile/{df['id']}"
        print(f"- {df['filename']} ({df['filesize']/1e6:.0f} MB)", flush=True)
        _download(url, dest, df["filesize"])
        expected = df.get("md5") or (df.get("checksum") or {}).get("value")
        if expected and _md5(dest) != expected:
            dest.unlink()
            raise SystemExit(f"체크섬 불일치: {dest.name} — 삭제했다. 다시 실행하라.")
        marker = out / f".extracted-{df['id']}"
        if not marker.exists():
            with zipfile.ZipFile(dest) as z:
                z.extractall(out)
            marker.touch()
    (out / "SOURCE.txt").write_text(
        f"{meta['citation']}\nLicense: {meta['license']}\n"
        "재배포하지 않는다. 학습·평가 목적으로만 로컬에 둔다.\n",
        encoding="utf-8",
    )
    return out


if __name__ == "__main__":
    for n in sys.argv[1:] or ["crackseg9k"]:
        print(f"== {n} → {fetch(n)}")
