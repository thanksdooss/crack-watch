"""학습·평가 스크립트 패키지.

병렬 워커마다 OpenCV·BLAS가 코어 수만큼 스레드를 또 띄우면, 워커 9개 × 스레드 10개로
기계가 수십 배 과부하에 걸린다(실제로 부하 평균 190을 찍었다). 병렬화는 프로세스 수준에서만
하고, 각 프로세스 안의 라이브러리 스레드는 1개로 묶는다.
"""

import os

for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_var, "1")

try:
    import cv2

    cv2.setNumThreads(1)
except ImportError:  # pragma: no cover
    pass


def workers() -> int:
    """병렬 워커 수: 코어의 절반(CRACK_WORKERS로 덮어쓰기). 이 기계는 개발자가 동시에 쓰고 있다."""
    return int(os.environ.get("CRACK_WORKERS") or max(1, (os.cpu_count() or 2) // 2))
