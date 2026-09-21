"""균열 세그멘테이션 학습.

    python -m ml.train.train --name unet-mnv3s --epochs 20

결과: data/runs/<name>/{best.pt,last.pt,log.jsonl}. 저장소에는 올리지 않는다(가중치는 export 후 배포).
선택 기준: val의 허용 F1(2px). 헛경보는 임계값 선택(ml.train.threshold)에서 따로 다룬다.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from ml.color.card import ROOT
from ml.datasets.crackseg9k import index
from ml.eval.metrics import Counts, count
from ml.train.data import CrackDataset
from ml.train.model import CrackUNet, count_params


def dice_loss(logits: torch.Tensor, target: torch.Tensor, eps: float = 1.0) -> torch.Tensor:
    """균열 픽셀이 1~3%뿐이라 BCE만 쓰면 '전부 배경'으로 쏠린다. Dice는 겹침 비율을 직접 민다."""
    p = torch.sigmoid(logits)
    inter = (p * target).sum(dim=(1, 2, 3))
    denom = p.sum(dim=(1, 2, 3)) + target.sum(dim=(1, 2, 3))
    return (1 - (2 * inter + eps) / (denom + eps)).mean()


def pad32(x: torch.Tensor) -> tuple[torch.Tensor, tuple[int, int]]:
    h, w = x.shape[-2:]
    ph, pw = (32 - h % 32) % 32, (32 - w % 32) % 32
    return F.pad(x, (0, pw, 0, ph), mode="reflect"), (h, w)


@torch.no_grad()
def validate(model, loader, device) -> dict:
    model.eval()
    tot, fa, neg = Counts(), 0, 0
    for x, y in loader:
        xp, (h, w) = pad32(x.to(device))
        prob = torch.sigmoid(model(xp))[..., :h, :w].cpu().numpy()
        for p, g in zip(prob[:, 0], y[:, 0].numpy()):
            pred = (p >= 0.5).astype(np.uint8)
            if g.any():
                tot.add(count(pred, g))
            else:
                neg += 1
                fa += int(pred.sum() >= 30)
    return {"tol_f1": tot.tol_f1, "iou": tot.iou, "tol_p": tot.tol_precision,
            "tol_r": tot.tol_recall, "fa": fa / max(neg, 1)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="unet-mnv3s")
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--crop", type=int, default=352)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0, help="빠른 점검용: 학습 이미지 수 제한")
    args = ap.parse_args()

    torch.manual_seed(0)
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    out = Path(ROOT) / "data" / "runs" / args.name
    out.mkdir(parents=True, exist_ok=True)

    train_rows = index(split="train")
    if args.limit:
        train_rows = train_rows[: args.limit]
    train_ds = CrackDataset(train_rows, train=True, crop=args.crop)
    val_ds = CrackDataset(index(split="val"), train=False)
    train_dl = DataLoader(train_ds, batch_size=args.batch, shuffle=True, num_workers=args.workers,
                          persistent_workers=args.workers > 0, drop_last=True)
    val_dl = DataLoader(val_ds, batch_size=8, num_workers=args.workers)

    model = CrackUNet().to(device)
    enc = list(model.encoder.parameters())
    enc_ids = {id(p) for p in enc}
    rest = [p for p in model.parameters() if id(p) not in enc_ids]
    # 사전학습 인코더는 천천히, 새로 붙인 디코더는 빠르게
    opt = torch.optim.AdamW([{"params": enc, "lr": args.lr * 0.3}, {"params": rest, "lr": args.lr}],
                            weight_decay=1e-4)
    steps = args.epochs * len(train_dl)
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: min(1.0, s / 200) * 0.5 * (1 + math.cos(math.pi * min(s, steps) / steps)))

    print(f"device={device} params={count_params(model)/1e6:.2f}M train={len(train_ds)} val={len(val_ds)}",
          flush=True)
    best = -1.0
    log = (out / "log.jsonl").open("a")
    for epoch in range(args.epochs):
        model.train()
        train_ds.epoch = epoch
        t0, tl, n = time.time(), 0.0, 0
        for x, y in train_dl:
            x, y = x.to(device), y.to(device)
            logits = model(x)
            loss = F.binary_cross_entropy_with_logits(logits, y) + dice_loss(logits, y)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            sched.step()
            tl += loss.item() * len(x)
            n += len(x)
            if (n // len(x)) % 100 == 0:
                print(f"  epoch {epoch} step {n // len(x)}/{len(train_dl)} loss {tl / n:.4f} "
                      f"{time.time() - t0:.0f}s", flush=True)
        v = validate(model, val_dl, device)
        rec = {"epoch": epoch, "loss": tl / n, "sec": round(time.time() - t0), **v}
        log.write(json.dumps(rec) + "\n")
        log.flush()
        print(json.dumps({k: round(x, 4) if isinstance(x, float) else x for k, x in rec.items()}),
              flush=True)
        torch.save(model.state_dict(), out / "last.pt")
        if v["tol_f1"] > best:
            best = v["tol_f1"]
            torch.save(model.state_dict(), out / "best.pt")
    print(f"best val tol_f1 {best:.4f}")


if __name__ == "__main__":
    main()
