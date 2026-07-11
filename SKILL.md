---
name: pdf-gpt55-zh-translate
description: Translate English PDFs into Simplified Chinese with pdf2zh/PDFMathTranslate using OpenAI-compatible endpoints while preserving page layout, images, tables, symbols, and typography. Use when the user asks to translate a PDF to Chinese, preserve original formatting/photos, produce mono/bilingual translated PDFs, translate page-by-page to avoid losing progress, try an OpenAI-compatible API endpoint, or create a visible raster fallback PDF when PDF text does not display in a viewer.
---

# PDF Chinese Translation With Page-Safe Progress

## Core Workflow

Default to **single-page translation** for full documents. Do not run a whole PDF in one long job unless the user explicitly requests it or the PDF is only a few pages. Page-by-page translation prevents losing all progress when an API call, layout pass, or fallback stalls.

Use `scripts/translate_pdf_gpt55.py` as the default entry point for trial pages and single-page jobs. It wraps `pdf2zh` with stable settings:

- `--openaicompatible`
- model default `gpt-5.5`, but allow user-provided OpenAI-compatible models
- OpenAI-compatible base URL should be supplied with `--base-url` or an environment variable
- `--enhance-compatibility`
- `--primary-font-family sans-serif`
- `--watermark-output-mode no_watermark`
- `--no-auto-extract-glossary`
- optional preview PNG rendering
- optional raster PDF fallback

Do not hardcode API keys in the skill or output files. Read them from `MIKOTO_API_KEY`, `LOCAL_TRANSLATION_API_KEY`, or `OPENAI_COMPATIBLE_API_KEY`, or pass `--api-key`.

## Quick Trial

Run a 1-page trial before full translation. Confirm the API works, Chinese glyphs render, and the output PDF opens.

```bash
python <skill-dir>\scripts\translate_pdf_gpt55.py ^
  "C:\path\input.pdf" ^
  --output-dir "C:\path\output\trial_page_001" ^
  --api-key "%OPENAI_COMPATIBLE_API_KEY%" ^
  --base-url "https://api.example.com/v1" ^
  --model "gpt-5.5" ^
  --pages 1 ^
  --no-preview
```

## Full Document Strategy

For a full document:

1. Count pages first.
2. Translate each page separately with `--pages N --only-translated-pages`.
3. Use `--no-preview` during translation for speed.
4. Allow at most 2-3 page jobs in parallel by default. More page jobs can exhaust memory because each job loads the local ONNX layout model.
5. Save each page output in a numbered folder such as `page_001`, `page_002`, etc.
6. If a page fails or stalls, stop only that page job and rerun that page with lower concurrency or a stricter prompt.
7. Merge completed `*.zh.dual.pdf` files in page order after every page has succeeded.

Use `qps=2` and `workers=2` as the normal speed/stability setting. Drop to `qps=1 workers=1` for pages with repeated fallback, tables, diagrams, or API instability.

## Single-Page Command

```bash
python <skill-dir>\scripts\translate_pdf_gpt55.py ^
  "C:\path\input.pdf" ^
  --output-dir "C:\path\output\page_001" ^
  --api-key "%OPENAI_COMPATIBLE_API_KEY%" ^
  --base-url "https://api.example.com/v1" ^
  --model "gpt-5.5" ^
  --pages 1 ^
  --qps 2 ^
  --workers 2 ^
  --no-preview
```

The wrapper adds `--only-include-translated-page` when `--pages` is set, so each output PDF contains only that page.

## Merge Page PDFs

After all single-page jobs complete, merge the bilingual PDFs in numeric page order:

```python
import fitz
from pathlib import Path

root = Path(r"C:\path\output")
out = root / "final.zh.dual.pdf"
merged = fitz.open()

for page_dir in sorted(root.glob("page_*")):
    pdfs = sorted(page_dir.glob("*.zh.dual.pdf"))
    if not pdfs:
        raise SystemExit(f"missing dual PDF in {page_dir}")
    with fitz.open(str(pdfs[0])) as doc:
        merged.insert_pdf(doc)

merged.save(str(out), deflate=True)
print(out)
```

## Deliverables

Report these paths to the user:

- `*.zh.mono.pdf`: Chinese-only translated PDF.
- `*.zh.dual.pdf`: bilingual PDF.
- `final.zh.dual.pdf` or equivalent merged bilingual PDF when page-by-page translation is used.
- `preview_pages/page_N.png`: rendered preview images when `--preview` is used.
- `*_visible_raster.pdf`: image-backed visible fallback when `--rasterize` is used.

Prefer the bilingual PDF when the user asks for Chinese-English side-by-side output. Use the raster fallback only when the user says text is invisible in their PDF viewer, because raster text cannot be copied.

## Recommended Options

Use `--pages 1 --no-preview` for trials. Use page-by-page translation for full documents. Use `--rasterize` only after checking the normal PDF.

For better terminology consistency, pass a glossary TSV if the user provides one:

```bash
--glossary C:\path\glossary.tsv
```

For agricultural equipment manuals, keep terminology consistent. If a glossary is needed, create a TSV glossary in UTF-8 and pass it with `--glossary`; do not rely on ad hoc model wording for repeated hardware terms such as feed bin, bin bolt, serrated flange nut, and safety decal.

## Reducing Fallback

Fallback means pdf2zh rejected a model response and retried with a simpler translation path. It slows translation greatly. To reduce fallback:

- Prefer models that obey "translation only" instructions.
- Keep temperature low, such as `0.1`.
- Use stricter prompts when calling raw `pdf2zh`: translate only to Simplified Chinese, preserve numbers/placeholders/units/part numbers, return text only, no explanations, no Markdown, no JSON.
- Split troublesome ranges into single pages.
- Lower concurrency for troublesome pages.

## Quality Check

After translation:

1. Render the original PDF and final translated PDF to PNGs after merging.
2. Compare pages visually, not only by whether the PDF opens.
3. Inspect pages with TOCs, dotted leaders, photos, diagrams, tables, and dense text.
4. Check that images are not missing and Chinese glyphs are visible.
5. If a page's layout differs too much from the original, rerun or manually replace that page only.
6. Pay special attention to TOC pages. Dotted leaders and page-number alignment often degrade; rerun that page with shorter terms or replace it separately.
7. If local viewer text is invisible but rendered PNGs look correct, run again with `--rasterize`.

## Known Failure Modes

- Some PDFs have broken embedded text layers. `pdf2zh` may still preserve layout, but extracted text may be imperfect.
- Directory/table-of-contents pages may lose dotted leaders or compact alignment.
- OpenAI-compatible models may vary terminology without a glossary. Add a TSV glossary for full-document runs.
- Long-running whole-document jobs can stall during fallback and lose progress if interrupted. Avoid whole-document jobs.
- Running too many page jobs at once can exhaust local memory because each job loads the layout model. Use at most 2-3 parallel jobs by default, and reduce to 1-2 for memory-constrained machines or complex pages.
- Raster fallback is visually stable but not selectable/searchable.
