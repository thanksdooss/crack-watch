"""docs/results/*.json → docs/evaluation.md. 숫자를 손으로 옮겨 적지 않는다."""

from __future__ import annotations

import json
from pathlib import Path

from ml.color.card import ROOT

RESULTS = Path(ROOT) / "docs" / "results"
OUT = Path(ROOT) / "docs" / "evaluation.md"

LABEL = {
    "classic": "고전 CV (기준선)",
}
SOURCE_LABEL = {
    "rissbilder": "Rissbilder (건물 외벽)",
    "volker": "Volker (건물 외벽)",
    "masonry": "Masonry (벽돌 벽)",
    "crack500": "CRACK500 (포장도로)",
    "cracktree": "CrackTree (포장도로)",
    "ceramic": "Ceramic (타일)",
    "noncrack": "Noncrack (균열 없는 콘크리트 벽)",
}


def _pct(v: float) -> str:
    return f"{v*100:.1f}%"


def _f(v: float) -> str:
    return f"{v:.3f}"


def render() -> None:
    results = {p.stem: json.loads(p.read_text(encoding="utf-8"))
               for p in sorted(RESULTS.glob("*.json"))}
    order = sorted(results, key=lambda k: (k != "classic", k))
    L: list[str] = []
    a = L.append
    a("# 평가 — 기준선 대비 얼마나 나은가\n")
    a("`python -m ml.eval.detection <엔진>` → `python -m ml.eval.detection render`로 다시 만든다.")
    a("이 파일의 숫자는 `docs/results/*.json`에서 자동으로 옮긴 것이다.\n")
    a("## 지표 읽는 법\n")
    a("- **정밀도**: 균열이라고 표시한 것 중 진짜 균열의 비율. 낮으면 헛신고가 많다.")
    a("- **재현율**: 진짜 균열 중 찾아낸 비율. 낮으면 놓친다.")
    a("- **F1**: 둘의 조화평균. 한쪽만 좋아서는 올라가지 않는다.")
    a("- **IoU**: 표시한 영역과 정답 영역이 겹친 정도. 1px만 어긋나도 깎이는 엄격한 지표.")
    a("- **허용 F1(2px)**: 정답에서 2px 안이면 맞춘 것으로 친다. 1~2px짜리 균열은 라벨 경계 자체가")
    a("  ±1px 흔들려서, 엄격 IoU만 보면 방법 간 차이가 라벨 잡음에 묻힌다.")
    a("- **헛경보율**: 균열 없는 벽 사진에서 '균열 있음'이라고 한 비율. 제품에서 가장 비싼 실수.")
    a("- 정확도(accuracy)는 쓰지 않는다 — 균열은 이미지의 1~3%라 전부 배경이라고 답해도 97%가 나온다.\n")

    a("## 1. 실제 사진 — CrackSeg9k test\n")
    a("건물 벽면(Rissbilder·Volker·Masonry)이 우리 제품이 실제로 찍힐 표면이다.\n")
    a("| 엔진 | 벽면 IoU | 벽면 정밀도 | 벽면 재현율 | 벽면 허용 F1 | 균열 없는 벽 헛경보 | 처리 시간(중앙값) |")
    a("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for k in order:
        r = results[k]["crackseg9k"]
        w = r["wall"]
        fa = r["false_alarm"].get("noncrack", {"rate": float("nan"), "hits": 0, "n": 0})
        a(f"| {LABEL.get(k, k)} | {_f(w['iou'])} | {_pct(w['precision'])} | {_pct(w['recall'])} | "
          f"**{_f(w['tol_f1'])}** | {_pct(fa['rate'])} ({fa['hits']}/{fa['n']}) | "
          f"{r['ms_per_image']:.0f} ms |")
    a("")
    a("### 출처별 (허용 F1 / IoU)\n")
    sources = sorted({s for k in order for s in results[k]["crackseg9k"]["per_source"]})
    a("| 출처 | " + " | ".join(LABEL.get(k, k) for k in order) + " |")
    a("| --- |" + " ---: |" * len(order))
    for s in sources:
        cells = []
        for k in order:
            v = results[k]["crackseg9k"]["per_source"].get(s)
            cells.append(f"{_f(v['tol_f1'])} / {_f(v['iou'])}" if v else "—")
        n = results[order[0]]["crackseg9k"]["per_source"].get(s, {}).get("n", "")
        a(f"| {SOURCE_LABEL.get(s, s)} (n={n}) | " + " | ".join(cells) + " |")
    a("")

    a("## 2. 합성 test — 정답 폭을 아는 세트\n")
    a("> 합성 데이터다. 빗물 자국·거푸집 이음선·기공 같은 '균열처럼 생긴 가짜'를 일부러 넣었다.")
    a("> 실제 성능의 증거가 아니라, 무엇에 속는지를 조절하며 보는 실험대다.\n")
    a("| 엔진 | IoU | 정밀도 | 재현율 | 허용 F1 | 헛경보 (균열 없는 벽) |")
    a("| --- | ---: | ---: | ---: | ---: | ---: |")
    for k in order:
        r = results[k]["synth"]
        a(f"| {LABEL.get(k, k)} | {_f(r['iou'])} | {_pct(r['precision'])} | {_pct(r['recall'])} | "
          f"**{_f(r['tol_f1'])}** | {_pct(r['false_alarm'])} "
          f"({round(r['false_alarm']*r['n_neg'])}/{r['n_neg']}) |")
    a("")
    a("## 평가 규칙\n")
    a("- 파라미터·모델 선택은 합성 dev와 CrackSeg9k val에서만 한다. test는 보고용으로만 쓴다.")
    a("- CrackSeg9k 분할은 **원본 사진 단위**로 나눴다. 한 장을 잘라 만든 조각들이 train과 test에")
    a("  갈라져 들어가면 test가 train을 베낀 셈이 되어 점수가 부풀려진다.")
    a("- 비상업·등록 조건이 명시된 하위 세트(DeepCrack·CFD·GAPs)는 학습과 평가 모두에서 뺐다.")
    a("- 처리 시간은 파이썬·데스크톱 CPU 기준이다. 브라우저·휴대폰 시간은 따로 잰다.")
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
