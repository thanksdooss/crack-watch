"""색 보정 검증 — 합성 조명에서 보정 전후 색 오차와 '붉은가' 판정 정확도를 잰다.

    python -m ml.eval.color_calibration        # docs/color-calibration.md 갱신

두 가지를 본다.
1. 색 오차표: 조명이 바뀌었을 때 색이 얼마나 틀어지고, 보정이 얼마나 되돌리는가.
   계수는 무채색 스와치에서만 구하고, 빨강·파랑은 계산에 넣지 않은 채 검증에만 쓴다.
2. 판정 시험: 이 프로젝트가 실제로 답해야 하는 질문 — "표지가 붉게 변했는가".
   보정 없이 석양 아래에서 찍으면 파란 표지도 붉어 보인다. 그게 오경보가 된다.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ml.color import calibrate
from ml.color.card import ROOT, chromatic_names, swatches, target_srgb
from ml.color.difference import delta_e_2000, srgb_to_lab
from ml.color.simulate import CaptureConditions, capture

SEED = 20260921
NOISE = 0.012  # 픽셀 하나 기준. 스와치 면적 평균으로 √n만큼 줄어든다

SCENARIOS: list[tuple[str, CaptureConditions]] = [
    ("맑은 날 바깥 (주광)", CaptureConditions("주광 D65", awb_strength=0.90, exposure=1.00, flare=0.00, noise_sigma=NOISE)),
    ("흐린 날 바깥", CaptureConditions("흐린 하늘 D75", awb_strength=0.80, exposure=0.90, flare=0.01, noise_sigma=NOISE)),
    ("건물 안 형광등", CaptureConditions("형광등 F2", awb_strength=0.70, exposure=0.80, flare=0.02, noise_sigma=NOISE)),
    ("백열등 아래", CaptureConditions("백열등 A", awb_strength=0.60, exposure=0.70, flare=0.02, noise_sigma=NOISE)),
    ("해질 무렵", CaptureConditions("석양 2500K", awb_strength=0.50, exposure=0.60, flare=0.03, noise_sigma=NOISE)),
    ("해질 무렵 + 역광", CaptureConditions("석양 2500K", awb_strength=0.50, exposure=0.50, flare=0.08, noise_sigma=NOISE)),
]

# 필름의 두 상태를 나타내는 '가정한' 색이다. 실제 필름을 측정한 값이 아니다.
# 우리가 만드는 것은 필름이 아니라 "사진 속 색을 믿을 수 있게 만드는 절차"이고,
# 이 실험은 그 절차가 조명 변화에 견디는지만 본다.
FILM_BLUE = np.array([60, 70, 160]) / 255
FILM_RED = np.array([180, 60, 55]) / 255
FILM_T = np.array([0.0, 0.125, 0.25, 0.375, 0.625, 0.75, 0.875, 1.0])  # 0.5(애매 구간)는 뺀다


def film_states() -> np.ndarray:
    """파랑 → 빨강 중간 단계들을 Lab에서 선형 보간해 만든다."""
    lab_a = np.atleast_2d(srgb_to_lab(FILM_BLUE))[0]
    lab_b = np.atleast_2d(srgb_to_lab(FILM_RED))[0]
    labs = np.array([lab_a + t * (lab_b - lab_a) for t in FILM_T])
    return labs


def judge_red(lab: np.ndarray) -> np.ndarray:
    """'붉은가'를 기준 두 색 중 가까운 쪽으로 판정한다."""
    ref_blue = np.atleast_2d(srgb_to_lab(FILM_BLUE))
    ref_red = np.atleast_2d(srgb_to_lab(FILM_RED))
    lab = np.atleast_2d(lab)
    d_blue = delta_e_2000(lab, np.repeat(ref_blue, len(lab), axis=0))
    d_red = delta_e_2000(lab, np.repeat(ref_red, len(lab), axis=0))
    return np.atleast_1d(d_red) < np.atleast_1d(d_blue)


def lab_to_srgb_via_states() -> np.ndarray:
    """필름 상태(Lab)를 다시 sRGB로. 촬영 시뮬레이터 입력이 sRGB라서 필요하다."""
    from ml.color.difference import XYZ_TO_RGB, linear_to_srgb

    labs = film_states()
    fy = (labs[:, 0] + 16) / 116
    fx = fy + labs[:, 1] / 500
    fz = fy - labs[:, 2] / 200
    eps, kappa = 216 / 24389, 24389 / 27
    def finv(t: np.ndarray) -> np.ndarray:
        return np.where(t**3 > eps, t**3, (116 * t - 16) / kappa)
    from ml.color.difference import D65
    xyz = np.stack([finv(fx), finv(fy), finv(fz)], axis=-1) * D65
    return linear_to_srgb(np.clip(xyz @ XYZ_TO_RGB.T, 0, 1))


def run() -> str:
    rng = np.random.default_rng(SEED)
    names = [s.name for s in swatches()]
    tgt = target_srgb(names)
    tgt_lab = srgb_to_lab(tgt)
    chroma_idx = [names.index(n) for n in chromatic_names()]
    neutral_idx = [i for i in range(len(names)) if i not in chroma_idx]

    film_srgb = lab_to_srgb_via_states()
    truth = FILM_T > 0.5

    rows = []
    judge_rows = []
    for label, cond in SCENARIOS:
        obs = capture(tgt, cond, rng)
        obs_lab = srgb_to_lab(obs)
        corr = calibrate.fit(obs, names)
        fixed_lab = srgb_to_lab(corr.apply_srgb(obs))

        def mean_de(idx: list[int], lab: np.ndarray) -> float:
            return float(np.mean(delta_e_2000(lab[idx], tgt_lab[idx])))

        rows.append(
            {
                "label": label,
                "neutral_before": mean_de(neutral_idx, obs_lab),
                "neutral_after": mean_de(neutral_idx, fixed_lab),
                "chroma_before": mean_de(chroma_idx, obs_lab),
                "chroma_after": mean_de(chroma_idx, fixed_lab),
                "quality": corr.quality,
            }
        )

        film_obs = capture(film_srgb, cond, rng)
        before = judge_red(srgb_to_lab(film_obs))
        after = judge_red(srgb_to_lab(corr.apply_srgb(film_obs)))
        judge_rows.append(
            {
                "label": label,
                "before_acc": float(np.mean(before == truth)),
                "after_acc": float(np.mean(after == truth)),
                "before_false_red": int(np.sum(before & ~truth)),
                "after_false_red": int(np.sum(after & ~truth)),
                "n_blue": int(np.sum(~truth)),
            }
        )

    return render(rows, judge_rows)


def render(rows: list[dict], judge_rows: list[dict]) -> str:
    out: list[str] = []
    a = out.append
    a("# 색 보정 — 조명이 달라도 같은 색으로 읽히는가\n")
    a("`python -m ml.eval.color_calibration`으로 다시 만든다. 난수 시드 고정.\n")
    a("> **합성 실험이다.** 실제 스마트폰으로 찍은 사진이 아니라, 조명에 따른 색 이동을")
    a("> 표준 색순응 모델로 흉내 낸 값이다. 알고리즘이 원리대로 도는지를 보는 것이고,")
    a("> 실촬영 측정치는 아래 '아직 비어 있는 칸'에 따로 채운다.\n")
    a("## 읽는 법\n")
    a("ΔE00은 사람이 느끼는 색 차이를 재는 표준 단위다. 대략 **1이면 훈련된 눈이 겨우")
    a("구분**, 2~3이면 나란히 놓으면 다르다는 걸 알아보는 정도, 10을 넘으면 누가 봐도 다른 색이다.\n")
    a("보정 계수는 **무채색(흰·회색·검정) 스와치에서만** 구한다. 빨강·파랑은 계산에 넣지 않고")
    a("검증에만 쓴다. 전부 넣고 맞추면 잘 맞는 게 당연해서 숫자가 아무것도 증명하지 못한다.\n")
    a("## 1. 색 오차 (ΔE00 평균)\n")
    a("| 조명 | 무채색 보정 전 | 무채색 보정 후 | **검증색(빨강·파랑) 보정 전** | **보정 후** | 판정 |")
    a("| --- | ---: | ---: | ---: | ---: | --- |")
    for r in rows:
        a(
            f"| {r['label']} | {r['neutral_before']:.2f} | {r['neutral_after']:.2f} | "
            f"**{r['chroma_before']:.2f}** | **{r['chroma_after']:.2f}** | {r['quality']} |"
        )
    worst = max(rows, key=lambda r: r["chroma_before"])
    a("")
    a(f"가장 나쁜 조건은 «{worst['label']}»으로, 보정 전 검증색 오차가 "
      f"{worst['chroma_before']:.1f}이다 — 누가 봐도 다른 색으로 찍혔다는 뜻이다. "
      f"보정 후 {worst['chroma_after']:.1f}까지 내려간다.\n")
    a("## 2. '붉게 변했는가' 판정\n")
    a("캠페인이 실제로 묻는 질문이다. 표지의 여러 중간 상태를 각 조명에서 찍었다고 보고,")
    a("보정 전후로 파랑/빨강 판정이 맞는지 센다. **거짓 빨강**은 파란 상태를 붉다고 잘못 읽은")
    a("횟수 — 그대로 오경보가 된다.\n")
    a("| 조명 | 보정 전 정확도 | 보정 후 정확도 | 보정 전 거짓 빨강 | 보정 후 거짓 빨강 |")
    a("| --- | ---: | ---: | ---: | ---: |")
    for j in judge_rows:
        a(
            f"| {j['label']} | {j['before_acc']*100:.0f}% | {j['after_acc']*100:.0f}% | "
            f"{j['before_false_red']} / {j['n_blue']} | {j['after_false_red']} / {j['n_blue']} |"
        )
    tot_before = sum(j["before_false_red"] for j in judge_rows)
    tot_after = sum(j["after_false_red"] for j in judge_rows)
    tot_blue = sum(j["n_blue"] for j in judge_rows)
    a("")
    a(f"전체 합계: 거짓 빨강 **{tot_before}/{tot_blue} → {tot_after}/{tot_blue}**.\n")
    a("판정에 쓴 필름의 파랑·빨강 색값은 **가정한 값**이다. 실제 필름을 측정한 것이 아니다.")
    a("우리가 만드는 것은 필름이 아니라 사진 속 색을 믿을 수 있게 만드는 절차이고,")
    a("이 실험은 그 절차가 조명 변화에 견디는지만 본다.\n")
    a("## 3. 아직 비어 있는 칸 (실촬영)\n")
    a("| 조명 | 기기 | 보정 전 ΔE00 | 보정 후 ΔE00 | 비고 |")
    a("| --- | --- | ---: | ---: | --- |")
    a("| 주광 | — | — | — | 미측정 |")
    a("| 형광등 | — | — | — | 미측정 |")
    a("| 석양 | — | — | — | 미측정 |")
    a("")
    a("`web/public/reference-card.pdf`를 100% 배율로 인쇄해 같은 벽면을 세 조명에서 찍으면")
    a("채울 수 있다. 인쇄물의 색이 설계값에서 벗어나는 것 자체가 오차 요인이라,")
    a("무채색만으로 계수를 잡는 지금 구조가 그 영향을 덜 받는다.\n")
    a("## 한계\n")
    a("- 합성 모델은 조명 변화를 von Kries 색순응으로 근사한다. 실제 카메라의 색 처리")
    a("  (톤 커브, 채도 강화, HDR 합성)는 더 복잡하고 기종마다 다르다.")
    a("- 스와치를 사진에서 찾아내는 검출 오차는 이 표에 들어 있지 않다. 검출은 다음 단계다.")
    a("- 인쇄 색 편차, 카드가 접히거나 젖는 경우, 그림자가 카드 일부에만 지는 경우는 미반영.")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    path = Path(ROOT) / "docs" / "color-calibration.md"
    path.write_text(run(), encoding="utf-8")
    print(f"wrote {path}")
