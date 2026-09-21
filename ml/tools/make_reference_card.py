"""인쇄용 기준 패치 카드(PDF)를 만든다.

    python -m ml.tools.make_reference_card

왜 라이브러리를 안 쓰나: 카드에 필요한 건 색 사각형과 ASCII 글자뿐이라 PDF를 직접
쓰는 편이 의존성 없이 결정적이다(같은 입력 → 바이트까지 같은 출력). 한글 안내문을
넣으려면 글꼴을 내장해야 해서 파일이 커지고 복잡해지므로, 카드에는 영문만 넣고
한글 안내는 앱 화면과 문서에서 한다.

치수·색은 ml/color/card.py와 shared/pipeline.json에서 읽는다. 여기서 다시 적지 않는다.
"""

from __future__ import annotations

from pathlib import Path

from ml.color.card import (
    CARD_H,
    CARD_W,
    FIDUCIAL_MARGIN,
    FIDUCIAL_SIZE,
    ROOT,
    RULER_LEN,
    RULER_X0,
    RULER_Y0,
    SWATCH_MM,
    swatches,
)

MM = 72 / 25.4  # 1mm를 PDF 단위(pt)로
PAGE_W, PAGE_H = 210.0, 297.0  # A4 (mm)
CARD_X0 = (PAGE_W - CARD_W) / 2
CARD_Y0 = PAGE_H - 45.0 - CARD_H

INSTRUCTIONS = [
    "1. Print at 100% scale. Do NOT use 'fit to page'.",
    "2. Check the bar on the card with a ruler: it must be exactly 60 mm.",
    "3. Tape the card flat on the wall, right next to the crack.",
    "4. Photograph the crack and the WHOLE card in one shot.",
    "",
    "The four black squares give the scale (px -> mm) and correct the viewing angle.",
    "The grey swatches fix the colour; the red and blue ones only verify it.",
    "",
    "This card does not diagnose safety. It only makes a photo measurable.",
]


def _rect(x: float, y: float, w: float, h: float, rgb: tuple[float, float, float]) -> str:
    r, g, b = rgb
    return f"{r:.4f} {g:.4f} {b:.4f} rg {x*MM:.3f} {y*MM:.3f} {w*MM:.3f} {h*MM:.3f} re f\n"


def _line(x1: float, y1: float, x2: float, y2: float, w_mm: float = 0.25) -> str:
    return (
        f"0 0 0 RG {w_mm*MM:.3f} w {x1*MM:.3f} {y1*MM:.3f} m "
        f"{x2*MM:.3f} {y2*MM:.3f} l S\n"
    )


def _text(x: float, y: float, size: float, s: str) -> str:
    escaped = s.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    return f"BT 0 0 0 rg /F1 {size:.1f} Tf {x*MM:.3f} {y*MM:.3f} Td ({escaped}) Tj ET\n"


def build_content() -> str:
    c = ""
    # 카드 테두리 (재단선)
    c += (
        f"0.6 0.6 0.6 RG 0.3 w {CARD_X0*MM:.3f} {CARD_Y0*MM:.3f} "
        f"{CARD_W*MM:.3f} {CARD_H*MM:.3f} re S\n"
    )
    c += _text(CARD_X0 + 15, CARD_Y0 + CARD_H - 6.5, 8, "CRACK-WATCH REFERENCE CARD  v1")

    # 네 모서리 기준 사각형 — 원근 보정과 px/mm 환산을 동시에 푼다
    for fx in (FIDUCIAL_MARGIN, CARD_W - FIDUCIAL_MARGIN - FIDUCIAL_SIZE):
        for fy in (FIDUCIAL_MARGIN, CARD_H - FIDUCIAL_MARGIN - FIDUCIAL_SIZE):
            c += _rect(CARD_X0 + fx, CARD_Y0 + fy, FIDUCIAL_SIZE, FIDUCIAL_SIZE, (0, 0, 0))

    for s in swatches():
        c += _rect(CARD_X0 + s.x_mm, CARD_Y0 + s.y_mm, SWATCH_MM, SWATCH_MM, s.srgb)
        c += (
            f"0.35 0.35 0.35 RG 0.2 w {(CARD_X0+s.x_mm)*MM:.3f} {(CARD_Y0+s.y_mm)*MM:.3f} "
            f"{SWATCH_MM*MM:.3f} {SWATCH_MM*MM:.3f} re S\n"
        )

    # 인쇄 배율 확인용 자 — 인쇄가 축소되면 모든 mm 환산이 틀어진다
    y = CARD_Y0 + RULER_Y0
    c += _line(CARD_X0 + RULER_X0, y, CARD_X0 + RULER_X0 + RULER_LEN, y, 0.4)
    for i in range(0, int(RULER_LEN) + 1, 10):
        tick = 2.5 if i % 50 else 4.0
        c += _line(CARD_X0 + RULER_X0 + i, y, CARD_X0 + RULER_X0 + i, y + tick, 0.4)
    c += _text(CARD_X0 + RULER_X0 - 1.5, y - 3.2, 6, "0")
    c += _text(CARD_X0 + RULER_X0 + RULER_LEN - 6, y - 3.2, 6, "60 mm")

    # 카드 밖 안내문
    ty = CARD_Y0 - 12
    c += _text(CARD_X0, ty, 10, "How to use")
    for i, line in enumerate(INSTRUCTIONS):
        c += _text(CARD_X0, ty - 6 - i * 5, 8.5, line)
    return c


def build_pdf() -> bytes:
    content = build_content().encode("latin-1")
    objs: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W*MM:.2f} {PAGE_H*MM:.2f}] "
            f"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ).encode("latin-1"),
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_at = len(out)
    out += f"xref\n0 {len(objs)+1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n"
    ).encode()
    return bytes(out)


if __name__ == "__main__":
    path = Path(ROOT) / "web" / "public" / "reference-card.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(build_pdf())
    print(f"wrote {path} ({path.stat().st_size} bytes)")
