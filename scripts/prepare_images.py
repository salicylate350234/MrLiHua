# -*- coding: utf-8 -*-
"""Prepare phone photos of an exam paper for transcription.

This script deliberately does NOT OCR.  It only makes the pages easier to read:
EXIF orientation, manual rotation, margin trimming, spread splitting, resizing,
contrast and sharpening.  The agent then reads the resulting page images with
the vision tool.

Examples:
    python scripts/prepare_images.py photos/*.jpg --out work/pages --rotate 90 --split
    python scripts/prepare_images.py photos/*.jpg --out work/pages --rotate 0 --trim 2 --scale 1.5
"""
from __future__ import annotations

import argparse
import glob
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


def expand_inputs(patterns: list[str]) -> list[Path]:
    files: list[Path] = []
    for pattern in patterns:
        matches = sorted(glob.glob(pattern))
        if not matches:
            p = Path(pattern)
            if p.exists():
                matches = [str(p)]
        for m in matches:
            p = Path(m)
            if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}:
                files.append(p)
    # de-duplicate while preserving order
    seen = set()
    out = []
    for p in files:
        key = str(p.resolve()).lower()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def process_one(
    path: Path,
    out_dir: Path,
    rotate: int,
    split: bool,
    trim_pct: float,
    scale: float,
    contrast: float,
    sharpen: bool,
    quality: int,
) -> list[Path]:
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")

    # rotate is clockwise degrees: 90 rotates the image clockwise.
    if rotate:
        im = im.rotate(-rotate, expand=True)

    if trim_pct > 0:
        w, h = im.size
        tx = int(w * trim_pct / 100)
        ty = int(h * trim_pct / 100)
        if w - 2 * tx > 100 and h - 2 * ty > 100:
            im = im.crop((tx, ty, w - tx, h - ty))

    pieces: list[tuple[str, Image.Image]] = []
    if split:
        w, h = im.size
        overlap = int(w * 0.02)
        pieces.append(("L", im.crop((0, 0, min(w, w // 2 + overlap), h))))
        pieces.append(("R", im.crop((max(0, w // 2 - overlap), 0, w, h))))
    else:
        pieces.append(("", im))

    written: list[Path] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    for suffix, piece in pieces:
        if scale and abs(scale - 1.0) > 0.001:
            piece = piece.resize(
                (max(1, int(piece.width * scale)), max(1, int(piece.height * scale))),
                Image.LANCZOS,
            )
        if contrast and abs(contrast - 1.0) > 0.001:
            piece = ImageEnhance.Contrast(piece).enhance(contrast)
        if sharpen:
            piece = piece.filter(ImageFilter.SHARPEN)
        name = f"{path.stem}{'_' + suffix if suffix else ''}.jpg"
        target = out_dir / name
        piece.save(target, quality=quality, optimize=True, subsampling=0)
        written.append(target)
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description="Prepare exam photos for vision transcription.")
    ap.add_argument("inputs", nargs="+", help="Image paths or glob patterns.")
    ap.add_argument("--out", type=Path, required=True, help="Output directory for prepared pages.")
    ap.add_argument(
        "--rotate",
        type=int,
        choices=[0, 90, 180, 270],
        default=0,
        help="Clockwise rotation to apply after EXIF correction (default: 0).",
    )
    ap.add_argument("--split", action="store_true", help="Split a two-page spread into L/R images.")
    ap.add_argument("--trim", type=float, default=0.0, help="Trim this percent from every edge (default: 0).")
    ap.add_argument("--scale", type=float, default=1.0, help="Resize factor (default: 1.0).")
    ap.add_argument("--contrast", type=float, default=1.08, help="Contrast factor (default: 1.08).")
    ap.add_argument("--no-sharpen", action="store_true", help="Disable the light sharpening pass.")
    ap.add_argument("--quality", type=int, default=93, help="JPEG quality (default: 93).")
    args = ap.parse_args()

    files = expand_inputs(args.inputs)
    if not files:
        print("No input images found.")
        return 1

    total = 0
    for path in files:
        written = process_one(
            path=path,
            out_dir=args.out,
            rotate=args.rotate,
            split=args.split,
            trim_pct=max(0.0, min(20.0, args.trim)),
            scale=max(0.2, min(4.0, args.scale)),
            contrast=max(0.5, min(2.0, args.contrast)),
            sharpen=not args.no_sharpen,
            quality=max(60, min(100, args.quality)),
        )
        total += len(written)
        for target in written:
            print(f"{path.name} -> {target}")
    print(f"Prepared {total} page image(s) in {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
