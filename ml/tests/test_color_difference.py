import numpy as np

from ml.color.difference import (
    delta_e_2000,
    linear_to_srgb,
    srgb_to_lab,
    srgb_to_linear,
)
from ml.color.card import FIXTURES


def test_ciede2000_matches_sharma_reference_data():
    """Sharma(2005) 34쌍 검증. 공식의 불연속 구간을 노린 값들이라 구현 실수를 걸러낸다."""
    rows = np.loadtxt(FIXTURES / "ciede2000_testdata.txt")
    assert len(rows) == 34
    got = delta_e_2000(rows[:, 0:3], rows[:, 3:6])
    np.testing.assert_allclose(got, rows[:, 6], atol=1e-4)


def test_srgb_linear_roundtrip():
    v = np.linspace(0, 1, 51)[:, None].repeat(3, axis=1)
    np.testing.assert_allclose(linear_to_srgb(srgb_to_linear(v)), v, atol=1e-9)


def test_identical_colors_have_zero_difference():
    lab = srgb_to_lab(np.array([[0.4, 0.2, 0.7]]))
    assert float(delta_e_2000(lab, lab)) < 1e-12


def test_white_maps_to_l100_neutral():
    # D65 백색점 상수가 반올림된 값이라 소수점 아래 미세 오차는 남는다.
    lab = np.atleast_2d(srgb_to_lab(np.array([1.0, 1.0, 1.0])))[0]
    assert abs(lab[0] - 100) < 1e-4
    assert abs(lab[1]) < 1e-3 and abs(lab[2]) < 1e-3
