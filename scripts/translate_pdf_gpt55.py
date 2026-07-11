#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


DEFAULT_BASE_URL = "https://api.example.com/v1"
DEFAULT_MODEL = "gpt-5.5"


def api_key_from_env() -> str:
    for name in ("OPENAI_COMPATIBLE_API_KEY", "LOCAL_TRANSLATION_API_KEY"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def run(command: list[str], cwd: Path | None = None) -> None:
    print("+ " + " ".join(command))
    subprocess.run(command, cwd=str(cwd) if cwd else None, check=True)


def render_previews(pdf: Path, out_dir: Path, scale: float) -> Path:
    import fitz  # type: ignore

    preview_dir = out_dir / "preview_pages"
    preview_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf))
    matrix = fitz.Matrix(scale, scale)
    for i, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        pix.save(preview_dir / f"page_{i}.png")
    return preview_dir


def rasterize_pdf(preview_dir: Path, out_pdf: Path, scale: float) -> Path:
    import fitz  # type: ignore
    from PIL import Image

    doc = fitz.open()
    images = sorted(preview_dir.glob("page_*.png"))
    if not images:
        raise RuntimeError(f"no preview images found in {preview_dir}")
    for image in images:
        with Image.open(image) as im:
            width, height = im.size
        page = doc.new_page(width=width / scale, height=height / scale)
        page.insert_image(page.rect, filename=str(image), keep_proportion=False)
    doc.save(str(out_pdf), deflate=True)
    return out_pdf


def find_outputs(output_dir: Path) -> tuple[Path | None, Path | None]:
    mono = sorted(output_dir.glob("*.zh.mono.pdf"))
    dual = sorted(output_dir.glob("*.zh.dual.pdf"))
    return (mono[0] if mono else None, dual[0] if dual else None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Translate PDFs to Simplified Chinese with pdf2zh and gpt-5.5.")
    parser.add_argument("pdf", type=Path, help="Input PDF path.")
    parser.add_argument("--output-dir", type=Path, help="Output directory. Defaults to <pdf-stem>_gpt55_zh.")
    parser.add_argument("--api-key", default=api_key_from_env(), help="API key. Defaults to OPENAI_COMPATIBLE_API_KEY/LOCAL_TRANSLATION_API_KEY.")
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_COMPATIBLE_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--model", default=os.environ.get("OPENAI_COMPATIBLE_MODEL", DEFAULT_MODEL))
    parser.add_argument("--pages", help="Page range for trial runs, e.g. 1-4 or 1,3,5-7.")
    parser.add_argument("--only-translated-pages", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--qps", default="1")
    parser.add_argument("--workers", default="1")
    parser.add_argument("--glossary", type=Path, help="Optional pdf2zh glossary TSV path.")
    parser.add_argument("--preview", action=argparse.BooleanOptionalAction, default=True, help="Render mono PDF to preview PNGs.")
    parser.add_argument("--preview-scale", type=float, default=1.5)
    parser.add_argument("--rasterize", action="store_true", help="Create image-backed fallback PDF from preview PNGs.")
    parser.add_argument("--timeout", default="7200")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.pdf.exists():
        raise SystemExit(f"input PDF not found: {args.pdf}")
    if not args.api_key:
        raise SystemExit("missing API key; set OPENAI_COMPATIBLE_API_KEY or pass --api-key")

    output_dir = args.output_dir or args.pdf.with_name(args.pdf.stem + "_gpt55_zh")
    output_dir.mkdir(parents=True, exist_ok=True)

    command = [
        "pdf2zh",
        str(args.pdf),
        "--lang-in",
        "en",
        "--lang-out",
        "zh",
        "--output",
        str(output_dir),
        "--openaicompatible",
        "--openai-compatible-model",
        args.model,
        "--openai-compatible-base-url",
        args.base_url,
        "--openai-compatible-api-key",
        args.api_key,
        "--openai-compatible-timeout",
        str(args.timeout),
        "--openai-compatible-temperature",
        "0.1",
        "--openai-compatible-send-temperature",
        "--enhance-compatibility",
        "--primary-font-family",
        "sans-serif",
        "--watermark-output-mode",
        "no_watermark",
        "--qps",
        str(args.qps),
        "--pool-max-workers",
        str(args.workers),
        "--no-auto-extract-glossary",
    ]
    if args.pages:
        command.extend(["--pages", args.pages])
        if args.only_translated_pages:
            command.append("--only-include-translated-page")
    if args.glossary:
        command.extend(["--glossaries", str(args.glossary)])

    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    print("+ " + " ".join(command[: command.index("--openai-compatible-api-key") + 1] + ["***"] + command[command.index("--openai-compatible-api-key") + 2 :]))
    subprocess.run(command, env=env, check=True)

    mono, dual = find_outputs(output_dir)
    print(f"mono_pdf={mono}")
    print(f"dual_pdf={dual}")

    if args.preview and mono:
        preview_dir = render_previews(mono, output_dir, args.preview_scale)
        print(f"preview_dir={preview_dir}")
        if args.rasterize:
            raster_pdf = output_dir / f"{args.pdf.stem}_visible_raster.pdf"
            rasterize_pdf(preview_dir, raster_pdf, args.preview_scale)
            print(f"raster_pdf={raster_pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
