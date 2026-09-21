"""학습된 모델 → ONNX(fp32) → 8비트 정수 양자화(int8) → 둘이 같은 답을 내는지 확인.

    python -m ml.export.onnx_export --run unet-mnv3s

양자화: 가중치와 중간값을 32비트 실수 대신 8비트 정수로 저장한다. 파일이 약 1/4로 줄고
휴대폰 CPU(WASM)에서 빨라지지만, 정밀도를 잃는다. 그래서 변환 직후 fp32와 int8의 결과
차이를 재서 기록한다 — 작다고 가정하지 않는다.

정적 양자화(QDQ)는 '보정용 입력'으로 각 층 값의 범위를 먼저 재야 한다. train 분할에서
뽑은 이미지를 쓴다(val·test는 쓰지 않는다).
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np
import torch

from ml.color.card import ROOT
from ml.datasets.crackseg9k import index
from ml.eval.metrics import Counts, count
from ml.train.data import load_pair, normalize
from ml.train.infer import FILES, MODEL_DIR, probability, session
from ml.train.model import CrackUNet

CALIB_N = 96
CHECK_N = 80


class _Calib:
    def __init__(self, rows, input_name: str):
        self.it = iter(rows)
        self.input_name = input_name

    def get_next(self):
        r = next(self.it, None)
        if r is None:
            return None
        img, _ = load_pair(r)
        img = img[:384, :384] if img.shape[0] >= 384 and img.shape[1] >= 384 else img
        return {self.input_name: normalize(img)[None]}


def export(run: str) -> dict:
    from onnxruntime.quantization import CalibrationMethod, QuantFormat, QuantType, quantize_static
    from onnxruntime.quantization.shape_inference import quant_pre_process

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model = CrackUNet(pretrained=False)
    model.load_state_dict(torch.load(Path(ROOT) / "data" / "runs" / run / "best.pt", map_location="cpu"))
    model.eval()

    fp32 = MODEL_DIR / FILES["model-fp32"]
    torch.onnx.export(model, torch.randn(1, 3, 384, 384), str(fp32), input_names=["image"],
                      output_names=["logits"], opset_version=17, dynamo=False,
                      dynamic_axes={"image": {2: "h", 3: "w"}, "logits": {2: "h", 3: "w"}})

    pre = MODEL_DIR / "crack_unet_pre.onnx"
    quant_pre_process(str(fp32), str(pre))
    rng = random.Random(0)
    calib_rows = rng.sample(index(split="train"), CALIB_N)
    int8 = MODEL_DIR / FILES["model-int8"]
    quantize_static(str(pre), str(int8), _Calib(calib_rows, "image"),
                    quant_format=QuantFormat.QDQ, per_channel=True,
                    activation_type=QuantType.QUInt8, weight_type=QuantType.QInt8,
                    calibrate_method=CalibrationMethod.MinMax)
    pre.unlink(missing_ok=True)
    session.cache_clear()

    # fp32와 int8이 같은 답을 내는가 — val에서 확인
    check = random.Random(1).sample(index(split="val"), CHECK_N)
    diffs, agree = [], Counts()
    for r in check:
        img, _ = load_pair(r)
        p32, p8 = probability("model-fp32", img), probability("model-int8", img)
        diffs.append(float(np.mean(np.abs(p32 - p8))))
        agree.add(count(p8 >= 0.5, p32 >= 0.5, tol=0))
    report = {
        "run": run,
        "fp32_mb": round(fp32.stat().st_size / 1e6, 2),
        "int8_mb": round(int8.stat().st_size / 1e6, 2),
        "mean_abs_prob_diff": float(np.mean(diffs)),
        "mask_iou_int8_vs_fp32": agree.iou,
        "n_checked": CHECK_N,
    }
    out = Path(ROOT) / "docs" / "results" / "export.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="unet-mnv3s")
    print(json.dumps(export(ap.parse_args().run), ensure_ascii=False, indent=1))
