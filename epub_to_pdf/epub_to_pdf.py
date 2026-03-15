#!/usr/bin/env python3
"""CLI utility to convert EPUB files to PDF using pandoc + TinyTeX.

Design goals:
- Self-contained runtime: installs Python dependency and downloads binaries when missing.
- Single PDF engine family: TinyTeX, using xelatex when available.
- Headless and cross-platform provisioning.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import shutil
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path


NETWORK_TIMEOUT_SECONDS = 45
DOWNLOAD_RETRIES = 3
RETRY_DELAY_SECONDS = 2

LOCAL_FONT_FILES: dict[str, str] = {
    "NotoSerif-Regular.ttf": "https://github.com/notofonts/noto-fonts/raw/main/hinted/ttf/NotoSerif/NotoSerif-Regular.ttf",
    "NotoSerif-Bold.ttf": "https://github.com/notofonts/noto-fonts/raw/main/hinted/ttf/NotoSerif/NotoSerif-Bold.ttf",
    "NotoSerif-Italic.ttf": "https://github.com/notofonts/noto-fonts/raw/main/hinted/ttf/NotoSerif/NotoSerif-Italic.ttf",
    "NotoSerif-BoldItalic.ttf": "https://github.com/notofonts/noto-fonts/raw/main/hinted/ttf/NotoSerif/NotoSerif-BoldItalic.ttf",
    "NotoSansMath-Regular.ttf": "https://github.com/notofonts/noto-fonts/raw/main/unhinted/ttf/NotoSansMath/NotoSansMath-Regular.ttf",
}

PROFILE_PRESETS: dict[str, dict[str, str | int]] = {
    "fiction": {"margin": "12mm", "dpi": 180},
    "math": {"margin": "15mm", "dpi": 300},
    "biology": {"margin": "10mm", "dpi": 300},
}


def get_local_fonts_dir() -> Path:
    """Return project-local directory used to store managed font files."""
    return Path(__file__).resolve().parent / "fonts"


def ensure_local_fonts_available(fonts_dir: Path | None = None) -> Path:
    """Ensure required local fonts exist in project folder (download if missing)."""
    target_dir = fonts_dir or get_local_fonts_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    for filename, url in LOCAL_FONT_FILES.items():
        target_file = target_dir / filename
        if not target_file.exists():
            print(f"Font '{filename}' not found. Downloading...")
            download_file(url, target_file)

    return target_dir


def ensure_python_dependency(import_name: str, pip_name: str | None = None):
    """Import dependency or install it on demand."""
    package_name = pip_name or import_name
    try:
        return importlib.import_module(import_name)
    except ModuleNotFoundError:
        print(f"Dependency '{package_name}' not found. Installing...")
        import subprocess
        import sys

        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        return importlib.import_module(import_name)


def ensure_pandoc_available(pypandoc_module) -> None:
    """Download pandoc automatically if missing."""
    try:
        pypandoc_module.get_pandoc_path()
    except OSError:
        print("Pandoc not found. Downloading pandoc binary...")
        pypandoc_module.download_pandoc()


def get_local_tinytex_dir() -> Path:
    """Return local install directory for managed TinyTeX."""
    if os.name == "nt":
        base = Path.home() / "AppData" / "Local"
    elif platform.system() == "Darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    return base / "epub_to_pdf" / "tinytex"


def tinytex_bin_candidates(tinytex_dir: Path) -> list[Path]:
    """Return likely TinyTeX bin directories by platform."""
    if os.name == "nt":
        return [
            tinytex_dir / "bin" / "windows",
            tinytex_dir / "bin" / "win32",
            tinytex_dir / "bin" / "win64",
        ]
    if platform.system() == "Darwin":
        return [
            tinytex_dir / "bin" / "universal-darwin",
            tinytex_dir / "bin" / "x86_64-darwin",
            tinytex_dir / "bin" / "arm64-darwin",
        ]
    return [
        tinytex_dir / "bin" / "x86_64-linux",
        tinytex_dir / "bin" / "aarch64-linux",
    ]


def add_to_path(directory: Path) -> None:
    """Prepend directory to PATH for this process."""
    parts = os.environ.get("PATH", "").split(os.pathsep)
    as_text = str(directory)
    if as_text not in parts:
        os.environ["PATH"] = f"{as_text}{os.pathsep}{os.environ.get('PATH', '')}"


def add_tinytex_to_path(tinytex_dir: Path) -> None:
    """Add TinyTeX bin directories to PATH for current process."""
    for candidate in tinytex_bin_candidates(tinytex_dir):
        if candidate.exists():
            add_to_path(candidate)


def find_engine_in_tinytex(tinytex_dir: Path, engine: str) -> str | None:
    """Find a LaTeX engine executable inside TinyTeX directory."""
    executable_name = f"{engine}.exe" if os.name == "nt" else engine

    for candidate in tinytex_bin_candidates(tinytex_dir):
        path = candidate / executable_name
        if path.exists():
            return str(path.resolve())

    discovered = next(tinytex_dir.rglob(executable_name), None)
    if discovered is not None:
        return str(discovered.resolve())

    return None


def download_file(url: str, destination: Path) -> None:
    """Download URL to destination path with retries."""
    last_error: Exception | None = None
    for attempt in range(1, DOWNLOAD_RETRIES + 1):
        try:
            with urllib.request.urlopen(url, timeout=NETWORK_TIMEOUT_SECONDS) as response, destination.open(
                "wb"
            ) as output:
                shutil.copyfileobj(response, output)
            return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < DOWNLOAD_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)

    raise RuntimeError(f"Failed to download '{url}': {last_error}")


def query_latest_tinytex_asset_url() -> tuple[str, str]:
    """Get TinyTeX asset URL and name for current platform from GitHub releases."""
    api_url = "https://api.github.com/repos/rstudio/tinytex-releases/releases/latest"
    request = urllib.request.Request(
        api_url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "epub-to-pdf-cli"},
    )
    with urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT_SECONDS) as response:
        payload = json.loads(response.read().decode("utf-8"))

    machine = platform.machine().lower()
    assets = payload.get("assets", [])

    if os.name == "nt":
        suffix = ".zip"
        prefers_arm = machine in ("arm64", "aarch64")
    elif platform.system() == "Darwin":
        suffix = ".tar.gz"
        prefers_arm = machine in ("arm64", "aarch64")
    else:
        suffix = ".tar.gz"
        prefers_arm = machine in ("arm64", "aarch64")

    def rank(name: str) -> tuple[int, int, int]:
        tinytex1 = 1 if name.startswith("TinyTeX-1-") else 0
        tinytex = 1 if name.startswith("TinyTeX-") else 0
        arm = 1 if "arm64" in name else 0
        arm_match = 1 if (arm == 1 and prefers_arm) or (arm == 0 and not prefers_arm) else 0
        return (tinytex1, tinytex, arm_match)

    compatible: list[tuple[tuple[int, int, int], dict]] = []
    for asset in assets:
        name = asset.get("name", "")
        if not name.endswith(suffix):
            continue
        if not (name.startswith("TinyTeX-1-") or name.startswith("TinyTeX-")):
            continue
        url = asset.get("browser_download_url")
        if not url:
            continue
        compatible.append((rank(name), asset))

    if not compatible:
        raise RuntimeError("Could not find a compatible TinyTeX release asset for this OS.")

    compatible.sort(key=lambda item: item[0], reverse=True)
    selected = compatible[0][1]
    return selected["browser_download_url"], selected["name"]


def ensure_tinytex_engine_available() -> str:
    """Ensure TinyTeX is installed and return Unicode-capable engine path."""
    tinytex_dir = get_local_tinytex_dir()

    if tinytex_dir.exists():
        add_tinytex_to_path(tinytex_dir)
        for engine in ("xelatex", "lualatex"):
            found = find_engine_in_tinytex(tinytex_dir, engine)
            if found:
                return found

    print("No TinyTeX engine found. Downloading TinyTeX (headless)...")
    tinytex_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="epub_to_pdf_tinytex_") as temp_dir:
        archive_url, archive_name = query_latest_tinytex_asset_url()
        archive_path = Path(temp_dir) / archive_name
        download_file(archive_url, archive_path)

        if os.name == "nt":
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(tinytex_dir)
        else:
            with tarfile.open(archive_path, "r:gz") as archive:
                archive.extractall(tinytex_dir)

    add_tinytex_to_path(tinytex_dir)
    for engine in ("xelatex", "lualatex"):
        found = find_engine_in_tinytex(tinytex_dir, engine)
        if found:
            print(f"Using TinyTeX engine '{Path(found).stem}'.")
            return found

    raise RuntimeError("TinyTeX was downloaded but no Unicode LaTeX engine (xelatex/lualatex) was found.")


def build_latex_header(text_layout: str, image_layout: str, engine_name: str) -> str:
    """Build optional LaTeX header for robust conversion."""
    lines: list[str] = []

    if engine_name in ("xelatex", "lualatex"):
        fonts_dir = ensure_local_fonts_available()
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
    """Convert one EPUB file to PDF."""
    if not input_file.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_file}")
    if input_file.suffix.lower() != ".epub":
        raise ValueError(f"Input file must be an EPUB: {input_file}")

    pypandoc = ensure_python_dependency("pypandoc")
    ensure_pandoc_available(pypandoc)
    pdf_engine = ensure_tinytex_engine_available()
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
