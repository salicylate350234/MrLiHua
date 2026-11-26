# -*- coding: utf-8 -*-
"""Local, free OCR for exam photos (RapidOCR / ONNX).

No network is used at runtime.  The engine and models are loaded locally.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageOps

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def collect_images(paths: Iterable[str]) -> list[Path]:
    out: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            out.extend(sorted(x for x in p.iterdir() if x.suffix.lower() in IMAGE_EXT))
        elif p.suffix.lower() in IMAGE_EXT and p.exists():
            out.append(p)
    # de-duplicate while preserving order
    seen = set()
    unique = []
    for p in out:
        key = str(p.resolve())
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def sort_lines(lines: list[dict]) -> list[dict]:
    # OCR line boxes are in image coordinates.  Group close y-values first so
    # options on the same visual line are read left-to-right.
    return sorted(
        lines,
        key=lambda x: (round(x["top"] / 18), x["left"], x["top"]),
    )


def ocr_image(engine, image: Image.Image, source: str, side: str) -> dict:
    import numpy as np

    arr = np.array(image.convert("RGB"))
    result, elapse = engine(arr)
    lines = []
    for item in result or []:
        box, text, conf = item[0], item[1], item[2]
        xs = [float(p[0]) for p in box]
        ys = [float(p[1]) for p in box]
        lines.append({
            "text": str(text),
            "box": [[round(float(x), 1), round(float(y), 1)] for x, y in box],
            "left": min(xs),
            "top": min(ys),
            "right": max(xs),
            "bottom": max(ys),
        })
    lines = sort_lines(lines)
    return {
        "source": source,
        "side": side,
        "width": image.width,
        "height": image.height,
        "lines": lines,
        "elapsed": elapse,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Local OCR for exam images (RapidOCR).")
    ap.add_argument("images", nargs="+", help="image files or directories")
    ap.add_argument("-o", "--out", default="ocr.json", help="output JSON")
    ap.add_argument("--split", action="store_true", help="split 4:3 spreads into left/right pages")
    ap.add_argument("--no-split", action="store_true", help="do not split (default)")
    ap.add_argument("--max-side", type=int, default=0, help="optional max image side; 0 keeps original")
    args = ap.parse_args()

    if args.split and args.no_split:
        ap.error("--split and --no-split are mutually exclusive")
    split = args.split and not args.no_split

    try:
        from rapidocr_onnxruntime import RapidOCR
    except Exception as exc:
        print("RapidOCR is not installed. Run: python -m pip install -r requirements-ocr.txt", file=sys.stderr)
        print(f"Import error: {exc}", file=sys.stderr)
        return 2

    paths = collect_images(args.images)
    if not paths:
        print("No images found.", file=sys.stderr)
        return 2

    engine = RapidOCR()
    pages = []
    for path in paths:
        try:
            image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        except Exception as exc:
            print(f"skip {path}: {exc}", file=sys.stderr)
            continue

        if args.max_side and max(image.size) > args.max_side:
            scale = args.max_side / max(image.size)
            image = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))), Image.LANCZOS)

        if split:
            mid = image.width // 2
            pages.append(ocr_image(engine, image.crop((0, 0, mid, image.height)), str(path), "L"))
            pages.append(ocr_image(engine, image.crop((mid, 0, image.width, image.height)), str(path), "R"))
        else:
            pages.append(ocr_image(engine, image, str(path), ""))

    data = {
        "version": 1,
        "engine": "rapidocr_onnxruntime",
        "split": split,
        "pages": pages,
        "lineCount": sum(len(p["lines"]) for p in pages),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OCR wrote {out} pages={len(pages)} lines={data['lineCount']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
