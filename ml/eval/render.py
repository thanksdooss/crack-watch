"""docs/results/*.json → docs/evaluation.md. 숫자를 손으로 옮겨 적지 않는다."""

from __future__ import annotations

import json
from pathlib import Path

from ml.color.card import ROOT

RESULTS = Path(ROOT) / "docs" / "results"
OUT = Path(ROOT) / "docs" / "evaluation.md"

LABEL = {
    "classic": "고전 CV (기준선)",
    "model-fp32": "U-Net+MobileNetV3 (32비트, 배포)",
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
               for p in sorted(RESULTS.glob("*.json")) if p.stem in LABEL}
    extra = {n: json.loads((RESULTS / f"{n}.json").read_text(encoding="utf-8"))
             for n in ("width", "quantization") if (RESULTS / f"{n}.json").exists()}
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
    if "classic" in results and "model-fp32" in results:
        c, m = results["classic"], results["model-fp32"]
        cw, mw = c["crackseg9k"]["wall"], m["crackseg9k"]["wall"]
        a("### 요약\n")
        a(f"실제 건물 벽면에서 모델의 허용 F1은 기준선의 **{mw['tol_f1'] / cw['tol_f1']:.1f}배**"
          f"({cw['tol_f1']:.3f} → {mw['tol_f1']:.3f}), IoU는 **{mw['iou'] / cw['iou']:.1f}배**"
          f"({cw['iou']:.3f} → {mw['iou']:.3f}). 균열 없는 벽 헛경보는 "
          f"{c['crackseg9k']['false_alarm']['noncrack']['rate']:.0%} → "
          f"{m['crackseg9k']['false_alarm']['noncrack']['rate']:.1%}.\n")
        a(f"반대로 합성 세트에서는 기준선이 {c['synth']['tol_f1']:.3f}, 모델이 {m['synth']['tol_f1']:.3f}다. "
          "합성 균열은 '배경 위의 깨끗한 검은 선'이라 고전 CV에 유리하고, 실제 사진으로 학습한 모델에게는 낯설다. "
          "합성 세트는 폭 정답이 필요한 실험(아래 3절)에만 쓰고 검출 성능 판단에는 쓰지 않는다.\n")
        a("기준선의 헛경보율은 분할마다 크게 흔들렸다(val 60장 10% → test 163장 51%). 민무늬 벽의 원본 사진 수가 "
          "적어 분할마다 벽 질감이 다르기 때문이다. 기준선은 벽 질감에 민감하다는 것 자체가 결과다.\n")

    if "width" in extra:
        a("## 3. 폭 추정 오차 (합성 test — 정답 폭을 앎)\n")
        a("기준 카드에서 오는 축척 오차는 빼고, **폭 측정 자체**의 오차만 본다. "
          "'검출 마스크'는 기준선이 낸 마스크로 잰 것 — 실제로 쓰일 조건이다.\n")
        names = {"mask_dt": "마스크 두께", "fwhm": "반치폭", "area": "넓이 기반", "hybrid": "**채택(혼합)**"}
        for cond, title in (("detected", "검출 마스크로 잼"), ("gt", "정답 마스크로 잼")):
            bins = extra["width"].get(cond, {})
            if not bins:
                continue
            a(f"**{title}** — 평균절대오차 mm (편향)\n")
            a("| 폭 구간 | n | " + " | ".join(names.values()) + " |")
            a("| --- | ---: |" + " ---: |" * len(names))
            for label, v in bins.items():
                cells = [f"{v[k]['mae_mm']:.3f} ({v[k]['bias_mm']:+.3f})" for k in names if k in v]
                a(f"| {label} | {v['n']} | " + " | ".join(cells) + " |")
            a("")
        a("마스크 두께로 재면 검출기의 이진화 임계에 폭이 끌려간다(0.3~1mm 구간에서 가장 크게 벌어짐). "
          "채택한 방법은 중심선을 따라 **원본 밝기 단면**에서 잰다: 폭 4px 미만은 넓이 기반(흐림에 강함), "
          "이상은 반치폭(균열 폭의 10%만큼 단면을 평활해 바닥의 기공에 끌려가지 않게). 남은 +0.1mm 안팎의 "
          "과대추정은 합성 데이터의 흐림 모델에서 나온 것이라 실제 사진에 그대로 빼지 않는다 — 과대추정은 "
          "'전문가 점검 권장' 쪽이라 안전한 방향이다.\n")

    if "quantization" in extra:
        q = extra["quantization"]
        a("## 4. 경량화 — 8비트 양자화를 채택하지 않은 이유\n")
        a("| 설정 | 크기 | 32비트 대비 마스크 IoU | 허용 F1 (val 60장) |")
        a("| --- | ---: | ---: | ---: |")
        for name, v in q.items():
            a(f"| {name} | {v['size_mb']:.2f} MB | {v['mask_iou_vs_fp32']:.3f} | {v['tol_f1']:.3f} |")
        a("")
        a("어떤 설정도 32비트를 따라가지 못했다. 디코더·출력층을 빼도 그대로라 문제는 인코더(MobileNetV3)이고, "
          "가중치만 양자화해도 무너진다 — 깊이별 합성곱은 채널마다 값 범위가 크게 달라 8비트 하나에 담기 어렵다. "
          "양자화를 고려한 재학습(QAT)이 다음 단계이고, 지금은 32비트(6.2MB, 목표 10MB 이하)를 배포한다.\n")

    a("## 평가 규칙\n")
    a("- 파라미터·모델·폭 측정 방법 선택은 합성 dev와 CrackSeg9k val에서만 한다. test는 보고용으로만 쓴다.")
    a("  (폭 측정 방법을 한때 합성 test로 비교했다가 되돌려 dev에서 다시 골랐다 — docs/decisions.md)")
    a("- CrackSeg9k 분할은 **원본 사진 단위**로 나눴다. 한 장을 잘라 만든 조각들이 train과 test에")
    a("  갈라져 들어가면 test가 train을 베낀 셈이 되어 점수가 부풀려진다.")
    a("- 비상업·등록 조건이 명시된 하위 세트(DeepCrack·CFD·GAPs)는 학습과 평가 모두에서 뺐다.")
    a("- 처리 시간은 파이썬·데스크톱 CPU 1스레드 기준이다. 브라우저·휴대폰 시간은 따로 잰다.")
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
