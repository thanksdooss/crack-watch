import cv2
import numpy as np

from ml.measure.skeleton import thin


def test_thin_line_becomes_one_pixel_wide():
    m = np.zeros((60, 120), np.uint8)
    cv2.line(m, (10, 30), (110, 30), 1, 7)
    sk = thin(m)
    cols = sk[:, 20:100].sum(axis=0)
    assert np.all(cols == 1), "직선은 열마다 정확히 한 픽셀만 남아야 한다"
    assert abs(np.nonzero(sk[:, 60])[0][0] - 30) <= 1, "중심선은 가운데에 있어야 한다"


def test_thin_keeps_connectivity_of_curve():
    m = np.zeros((100, 100), np.uint8)
    cv2.ellipse(m, (50, 50), (35, 20), 0, 0, 180, 1, 5)
    sk = thin(m)
    n, _ = cv2.connectedComponents(sk, connectivity=8)
    assert n - 1 == 1, "끊어지면 균열 하나가 여러 개로 세어진다"


def test_empty_mask():
    assert thin(np.zeros((10, 10), np.uint8)).sum() == 0
