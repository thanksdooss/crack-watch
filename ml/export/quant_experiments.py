"""8비트 양자화 실험 기록 — 왜 32비트 모델을 배포하는가.

    python -m ml.export.quant_experiments     # docs/results/quantization.json

val 60장에서 32비트 원본과의 균열 마스크 일치도(IoU)와 정답 대비 허용 F1을 잰다.
결과(2026-09-21): 어떤 설정도 원본을 따라가지 못했다. 디코더·출력층을 빼도 그대로고
(문제는 인코더), 가중치만 양자화해도 무너진다 — MobileNetV3의 깊이별 합성곱은 채널마다
값 범위가 크게 달라 8비트 하나로 담기 어렵다. 양자화를 고려한 재학습(QAT)이 다음 단계다.
"""

from __future__ import annotations

import json
import os
import random
import warnings
from pathlib import Path

import cv2
import numpy as np
import onnx
import onnxruntime as ort
from onnxruntime.quantization import (CalibrationMethod, QuantFormat, QuantType, quantize_dynamic,
                                      quantize_static)
from onnxruntime.quantization.shape_inference import quant_pre_process

from ml.color.card import ROOT
from ml.datasets.crackseg9k import index
from ml.eval.metrics import Counts, count
from ml.export.onnx_export import _Calib
from ml.train.data import load_pair, normalize

warnings.filterwarnings("ignore")
D = Path(ROOT) / "data" / "models"


def main() -> None:
    pre, fp32 = str(D / "pre.onnx"), str(D / "crack_unet_fp32.onnx")
    quant_pre_process(fp32, pre)
    names = [n.name for n in onnx.load(pre).graph.node]
    head = [n for n in names if n.startswith("/head")]
    dec_last = [n for n in names if n.startswith(("/decoders.3", "/decoders.2"))]
    decoder_all = [n for n in names if n.startswith(("/decoders", "/head", "/reduce"))]
    calib = random.Random(0).sample(index(split="train"), 96)
    check = random.Random(1).sample(index(split="val"), 60)

    def sess(path: str):
        o = ort.SessionOptions()
        o.intra_op_num_threads = 4
        return ort.InferenceSession(path, o, providers=["CPUExecutionProvider"])

    def probs(s, img):
        h, w = img.shape[:2]
        x = normalize(cv2.copyMakeBorder(img, 0, (32 - h % 32) % 32, 0, (32 - w % 32) % 32,
                                         cv2.BORDER_REFLECT))[None]
        return 1 / (1 + np.exp(-s.run(None, {"image": x})[0][0, 0, :h, :w]))

    imgs = [load_pair(r) for r in check]
    ref = sess(fp32)
    refp = [probs(ref, i) for i, _ in imgs]

    def evaluate(path: str) -> dict:
        s = sess(path)
        agree, gt, gt32 = Counts(), Counts(), Counts()
        for (img, m), p32 in zip(imgs, refp):
            p = probs(s, img)
            agree.add(count(p >= .5, p32 >= .5, tol=0))
            if m.any():
                gt.add(count(p >= .5, m))
                gt32.add(count(p32 >= .5, m))
        return {"size_mb": round(os.path.getsize(path) / 1e6, 2), "mask_iou_vs_fp32": agree.iou,
                "tol_f1": gt.tol_f1, "tol_f1_fp32": gt32.tol_f1}

    def static(**kw) -> str:
        out = str(D / "exp.onnx")
        quantize_static(pre, out, _Calib(calib, "image"), quant_format=QuantFormat.QDQ, per_channel=True,
                        activation_type=QuantType.QUInt8, weight_type=QuantType.QInt8, **kw)
        return out

    pct = dict(calibrate_method=CalibrationMethod.Percentile, extra_options={"CalibPercentile": 99.99})
    mm = dict(calibrate_method=CalibrationMethod.MinMax)
    results = {"fp32": evaluate(fp32)}
    for name, kw in {
        "정적 MinMax, 전체": dict(**mm),
        "정적 Percentile, 전체": dict(**pct),
        "정적 MinMax, 출력층 제외": dict(**mm, nodes_to_exclude=head),
        "정적 MinMax, 출력층+마지막 디코더 제외": dict(**mm, nodes_to_exclude=head + dec_last),
        "정적 MinMax, 인코더만": dict(**mm, nodes_to_exclude=decoder_all),
        "정적 Percentile, Conv만": dict(**pct, op_types_to_quantize=["Conv"]),
    }.items():
        results[name] = evaluate(static(**kw))
        print(name, results[name], flush=True)
    dyn = str(D / "exp_dyn.onnx")
    quantize_dynamic(pre, dyn, weight_type=QuantType.QUInt8, op_types_to_quantize=["Conv"])
    results["동적(가중치만)"] = evaluate(dyn)
    for f in ("pre.onnx", "exp.onnx", "exp_dyn.onnx"):
        (D / f).unlink(missing_ok=True)
    out = Path(ROOT) / "docs" / "results" / "quantization.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
