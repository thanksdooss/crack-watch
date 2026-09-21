"""U-Net + MobileNetV3 인코더. 브라우저(ONNX Runtime Web)에서 돌릴 것을 전제로 작게 만든다.

- 인코더: torchvision MobileNetV3-Small, ImageNet 사전학습 가중치(torchvision 배포, BSD-3).
  처음부터 학습하기엔 균열 데이터가 적다(수천 장). 이미 '가장자리·질감'을 아는 인코더에서 출발한다.
- 디코더: 업샘플 + 인코더의 같은 해상도 특징을 이어 붙임(skip). 균열은 1~3px라서, 해상도를
  32배 줄였다가 다시 키우는 동안 사라진 위치 정보를 skip이 되살린다.
- ONNX 호환: 업샘플은 bilinear(align_corners=False), 연산은 Conv/BN/ReLU/Hardswish만.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small

# mobilenet_v3_small.features에서 해상도가 바뀌기 직전 단계의 인덱스와 채널 수
SKIPS = [(0, 16), (1, 16), (3, 24), (8, 48)]  # stride 2, 4, 8, 16
BOTTOM = (12, 576)  # stride 32


class Block(nn.Sequential):
    def __init__(self, cin: int, cout: int):
        super().__init__(
            nn.Conv2d(cin, cout, 3, padding=1, bias=False), nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
            nn.Conv2d(cout, cout, 3, padding=1, bias=False), nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
        )


class CrackUNet(nn.Module):
    def __init__(self, pretrained: bool = True, width: int = 32):
        super().__init__()
        weights = MobileNet_V3_Small_Weights.IMAGENET1K_V1 if pretrained else None
        self.encoder = mobilenet_v3_small(weights=weights).features
        chans = [c for _, c in SKIPS]
        self.reduce = nn.Conv2d(BOTTOM[1], width * 4, 1)
        dec_in = width * 4
        self.decoders = nn.ModuleList()
        outs = [width * 4, width * 2, width, width]
        for skip_c, out_c in zip(reversed(chans), outs):
            self.decoders.append(Block(dec_in + skip_c, out_c))
            dec_in = out_c
        self.head = nn.Sequential(Block(dec_in + 3, width // 2), nn.Conv2d(width // 2, 1, 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        feats = {}
        h = x
        for i, layer in enumerate(self.encoder):
            h = layer(h)
            feats[i] = h
            if i == BOTTOM[0]:
                break
        h = self.reduce(h)
        for (idx, _), dec in zip(reversed(SKIPS), self.decoders):
            s = feats[idx]
            h = F.interpolate(h, size=s.shape[-2:], mode="bilinear", align_corners=False)
            h = dec(torch.cat([h, s], dim=1))
        h = F.interpolate(h, size=x.shape[-2:], mode="bilinear", align_corners=False)
        return self.head(torch.cat([h, x], dim=1))  # 원본 해상도 입력을 한 번 더 붙여 1px 균열을 살린다


def count_params(m: nn.Module) -> int:
    return sum(p.numel() for p in m.parameters())
