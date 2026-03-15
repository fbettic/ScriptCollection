#!/usr/bin/env python3
"""CLI utility to convert EPUB files to PDF using pandoc + TinyTeX.

Design goals:
- Assumes all dependencies are pre-installed (pypandoc, pandoc, xelatex/lualatex, fonts).
- Single PDF engine family: TinyTeX, using xelatex when available.
- Direct conversion without runtime provisioning.
"""

from __future__ import annotations

import argparse
import os
import shutil
import tempfile
from pathlib import Path


LOCAL_FONT_FILES: set[str] = {
    "NotoSerif-Regular.ttf",
    "NotoSerif-Bold.ttf",
    "NotoSerif-Italic.ttf",
    "NotoSerif-BoldItalic.ttf",
    "NotoSansMath-Regular.ttf",
}

PROFILE_PRESETS: dict[str, dict[str, str | int]] = {
    "fiction": {"margin": "12mm", "dpi": 180},
    "math": {"margin": "15mm", "dpi": 300},
    "biology": {"margin": "10mm", "dpi": 300},
}


def get_local_fonts_dir() -> Path:
    """Return project-local directory used to store font files."""
    return Path(__file__).resolve().parent / "fonts"


def build_latex_header(text_layout: str, image_layout: str, engine_name: str) -> str:
    """Build optional LaTeX header for robust conversion."""
    lines: list[str] = []

    if engine_name in ("xelatex", "lualatex"):
        fonts_dir = get_local_fonts_dir()
        latex_path = fonts_dir.as_posix()
        lines.extend(
            [
                r"\usepackage{fontspec}",
                r"\usepackage{unicode-math}",
                r"\defaultfontfeatures{Ligatures=TeX}",
                rf"\setmainfont[Path={{{latex_path}/}},Extension=.ttf,UprightFont=NotoSerif-Regular,BoldFont=NotoSerif-Bold,ItalicFont=NotoSerif-Italic,BoldItalicFont=NotoSerif-BoldItalic]{{Noto Serif}}",
                rf"\setmathfont[Path={{{latex_path}/}}]{{NotoSansMath-Regular.ttf}}",
            ]
        )

    if image_layout == "contain":
        lines.extend(
            [
                r"\usepackage{graphicx}",
                r"\makeatletter",
                r"\def\maxwidth{\ifdim\Gin@nat@width>\linewidth\linewidth\else\Gin@nat@width\fi}",
                r"\def\maxheight{\ifdim\Gin@nat@height>\textheight\textheight\else\Gin@nat@height\fi}",
                r"\setkeys{Gin}{width=\maxwidth,height=\maxheight,keepaspectratio}",
                r"\makeatother",
            ]
        )

    if text_layout == "adaptive":
        lines.extend(
            [
                r"\setlength{\emergencystretch}{5em}",
                r"\tolerance=1800",
                r"\hbadness=2500",
                r"\hfuzz=1pt",
                r"\vfuzz=1pt",
                r"\sloppy",
            ]
        )

    return "\n".join(lines)


def resolve_output_path(input_file: Path, output_file: str | None) -> Path:
    """Resolve output path using input path when output is omitted."""
    if output_file:
        return Path(output_file).expanduser().resolve()
    return input_file.with_suffix(".pdf")


def convert_epub_to_pdf(
    input_file: Path,
    output_file: Path,
    margin: str,
    dpi: int | None,
    text_layout: str,
    image_layout: str,
) -> None:
    """Convert one EPUB file to PDF (assumes all dependencies are installed)."""
    if not input_file.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_file}")
    if input_file.suffix.lower() != ".epub":
        raise ValueError(f"Input file must be an EPUB: {input_file}")

    import pypandoc

    pdf_engine = shutil.which("xelatex") or shutil.which("lualatex") or "pdflatex"
    engine_name = Path(pdf_engine).stem.lower()

    extra_args = [
        f"--pdf-engine={pdf_engine}",
        "-V",
        f"geometry:margin={margin}",
    ]
    if dpi is not None:
        extra_args.append(f"--dpi={dpi}")

    header = build_latex_header(text_layout=text_layout, image_layout=image_layout, engine_name=engine_name)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="epub_to_pdf_header_") as temp_dir:
        header_file = Path(temp_dir) / "layout.tex"
        header_file.write_text(header, encoding="utf-8")

        scoped_args = [*extra_args, "--include-in-header", str(header_file)]
        pypandoc.convert_file(
            str(input_file),
            "pdf",
            outputfile=str(output_file),
            extra_args=scoped_args,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert an EPUB file to PDF using pandoc + TinyTeX.")
    parser.add_argument("input_file", help="Path to the input EPUB file.")
    parser.add_argument(
        "output_file",
        nargs="?",
        help="Optional output PDF path. Defaults to input path with .pdf extension.",
    )
    parser.add_argument(
        "--profile",
        choices=["fiction", "math", "biology"],
        help="Preset optimized for fiction, math, or biology books.",
    )
    parser.add_argument(
        "--margin",
        help="PDF page margin for LaTeX geometry (e.g. 12mm, 1.5cm).",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        help="Image DPI hint for pandoc (useful for image-heavy books).",
    )
    parser.add_argument(
        "--text-layout",
        choices=["adaptive", "standard"],
        default="adaptive",
        help="Text line-breaking strategy. 'adaptive' reduces overfull/underfull warnings.",
    )
    parser.add_argument(
        "--image-layout",
        choices=["contain", "standard"],
        default="contain",
        help="Image fitting strategy. 'contain' scales oversized images to page bounds.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.input_file).expanduser().resolve()
    output_path = resolve_output_path(input_path, args.output_file)
    selected_profile = PROFILE_PRESETS.get(args.profile or "", {})

    margin_value = args.margin if args.margin is not None else selected_profile.get("margin", "18mm")
    margin = str(margin_value).strip()
    dpi_value = args.dpi if args.dpi is not None else selected_profile.get("dpi")
    dpi = int(dpi_value) if isinstance(dpi_value, int) else None
    text_layout = str(args.text_layout).strip()
    image_layout = str(args.image_layout).strip()

    if not margin:
        print("Error: --margin cannot be empty.")
        return 1

    if dpi is not None and dpi <= 0:
        print("Error: --dpi must be greater than 0.")
        return 1

    try:
        convert_epub_to_pdf(
            input_path,
            output_path,
            margin=margin,
            dpi=dpi,
            text_layout=text_layout,
            image_layout=image_layout,
        )
    except Exception as exc:  # pragma: no cover
        print(f"Error: {exc}")
        return 1

    print(f"PDF generated successfully: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
