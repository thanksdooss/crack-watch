import numpy as np
import pytest

from ml.color.card_raster import place
from ml.color.detect_card import CardDetection, detect
from ml.synth.wall import CrackSpec, WallSpec, generate


def _scene(seed: int, rot: float, tilt: tuple[float, float], ppm: float = 6.0):
    rng = np.random.default_rng(seed)
    wall = generate(rng, WallSpec(size_px=(600, 800), px_per_mm=6), [CrackSpec(width_mm=1)])
    return place(wall.image, (420, 300), ppm, rot, tilt)


@pytest.mark.parametrize("rot,tilt", [(0, (0, 0)), (97, (0.8, -0.5)), (-170, (-1.2, 1.0))])
def test_card_found_and_scale_recovered(rot, tilt):
    scene, H_true = _scene(11, rot, tilt)
    d = detect(scene)
    assert d is not None
    truth = CardDetection(H_true, {}, 0, None).px_per_mm_at(420, 300)
    assert abs(d.px_per_mm_at(420, 300) - truth) / truth < 0.01


def test_card_orientation_is_not_read_upside_down():
    """뒤집혀 읽으면 흰 칸 자리에서 검정을 읽는다. 색 보정이 통째로 뒤집힌다."""
    scene, _ = _scene(12, 180, (0, 0))
    d = detect(scene)
    assert d is not None
    assert d.swatch_srgb["white"].mean() > d.swatch_srgb["black"].mean() + 0.5


def test_no_card_returns_none():
    rng = np.random.default_rng(13)
    wall = generate(rng, WallSpec(size_px=(600, 800)), [CrackSpec(width_mm=1)])
    assert detect(wall.image) is None
