import numpy as np
import pytest

from ml.color import calibrate
from ml.color.card import (
    CARD_H,
    CARD_W,
    FIDUCIAL_CENTERS_MM,
    chromatic_names,
    neutral_names,
    swatches,
    target_srgb,
)
from ml.color.difference import delta_e_2000, srgb_to_lab
from ml.color.simulate import CaptureConditions, capture

NAMES = [s.name for s in swatches()]


def _mean_de(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.mean(delta_e_2000(srgb_to_lab(a), srgb_to_lab(b))))


def test_identity_capture_is_recovered_exactly():
    """아무 것도 안 바뀐 조건에서는 보정이 색을 건드리지 않아야 한다."""
    tgt = target_srgb(NAMES)
    corr = calibrate.fit(tgt, NAMES)
    np.testing.assert_allclose(corr.apply_srgb(tgt), tgt, atol=1e-6)
    assert corr.quality == "good"


@pytest.mark.parametrize("illuminant", ["형광등 F2", "백열등 A", "석양 2500K"])
def test_correction_reduces_error_on_held_out_colours(illuminant):
    """계수는 무채색에서만 구하는데, 계산에 넣지 않은 빨강·파랑도 제자리를 찾아야 한다."""
    tgt = target_srgb(NAMES)
    cond = CaptureConditions(illuminant, awb_strength=0.6, exposure=0.7, flare=0.02)
    obs = capture(tgt, cond)
    corr = calibrate.fit(obs, NAMES)
    fixed = corr.apply_srgb(obs)

    idx = [NAMES.index(n) for n in chromatic_names()]
    before = _mean_de(obs[idx], tgt[idx])
    after = _mean_de(fixed[idx], tgt[idx])
    assert before > 2.0, "이 조명에서는 원래 색이 눈에 띄게 틀어져 있어야 실험이 성립한다"
    assert after < before / 2, f"보정 후 오차가 절반 아래로 내려가야 한다 ({before:.2f} → {after:.2f})"


def test_flare_is_absorbed_by_the_offset_term():
    """잡광은 어두운 색을 들뜨게 한다. 검은 스와치가 그 오프셋을 잡아야 한다."""
    tgt = target_srgb(NAMES)
    obs = capture(tgt, CaptureConditions("주광 D65", awb_strength=1.0, flare=0.05))
    corr = calibrate.fit(obs, NAMES)
    assert np.all(corr.offset > 0.01)
    assert _mean_de(corr.apply_srgb(obs), tgt) < _mean_de(obs, tgt)


def test_fit_needs_at_least_two_neutrals():
    with pytest.raises(ValueError):
        calibrate.fit(target_srgb(["white"]), ["white"])


def test_card_geometry_is_consistent():
    assert len(swatches()) == 6
    assert len(neutral_names()) == 4 and len(chromatic_names()) == 2
    for s in swatches():
        assert 0 < s.x_mm < CARD_W and 0 < s.y_mm < CARD_H
    # 기준 사각형 네 개의 간격은 픽셀→mm 환산의 근거다. 값이 바뀌면 환산이 틀어진다.
    xs = sorted({c[0] for c in FIDUCIAL_CENTERS_MM})
    ys = sorted({c[1] for c in FIDUCIAL_CENTERS_MM})
    assert round(xs[1] - xs[0], 3) == 77.0
    assert round(ys[1] - ys[0], 3) == 43.0


def test_reference_card_pdf_is_deterministic():
    from ml.tools.make_reference_card import build_pdf

    assert build_pdf() == build_pdf()
    assert build_pdf().startswith(b"%PDF-")
