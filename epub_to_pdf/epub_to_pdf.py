#!/usr/bin/env python3
"""CLI utility to convert EPUB files to PDF using pandoc + TinyTeX.

Design goals:
- Standalone executable with embedded Python and fonts
- Automatic TinyTeX provisioning (downloaded on first run if needed)
- Cross-platform support (Windows, Linux, macOS) with PyInstaller
- Unicode font support with xelatex engine
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
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
    # Support PyInstaller bundled execution
    if getattr(sys, '_MEIPASS', None):
        return Path(sys._MEIPASS) / "fonts"
    return Path(__file__).resolve().parent / "fonts"


def get_tinytex_cache_dir() -> Path:
    """Return local cache directory for managed TinyTeX installation."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    elif platform.system() == "Darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    return base / "epub2pdf" / "tinytex"


def get_tinytex_bin_candidates(tinytex_dir: Path) -> list[Path]:
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


def find_xelatex_in_cache() -> str | None:
    """Find xelatex in TinyTeX cache directory."""
    tinytex_dir = get_tinytex_cache_dir()
    if not tinytex_dir.exists():
        return None
    
    executable_name = "xelatex.exe" if os.name == "nt" else "xelatex"
    
    for candidate in get_tinytex_bin_candidates(tinytex_dir):
        path = candidate / executable_name
        if path.exists():
            return str(path.resolve())
    
    # Fallback: recursive search
    discovered = next(tinytex_dir.rglob(executable_name), None)
    if discovered:
        return str(discovered.resolve())
    
    return None


def download_tinytex() -> None:
    """Download and extract TinyTeX to cache directory."""
    print("Downloading TinyTeX (this may take a few minutes)...")
    
    api_url = "https://api.github.com/repos/rstudio/tinytex-releases/releases/latest"
    request = urllib.request.Request(
        api_url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "epub2pdf"},
    )
    
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    
    machine = platform.machine().lower()
    assets = payload.get("assets", [])
    
    # TinyTeX releases use only extension to distinguish platform (no platform keywords in name)
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
        name_lower = name.lower()
        # Prefer TinyTeX-1 (minimal) over TinyTeX (full) and TinyTeX-0 (even smaller but maybe too minimal)
        tinytex1 = 2 if name.startswith("TinyTeX-1-") else 0
        tinytex = 1 if name.startswith("TinyTeX-") and not name.startswith("TinyTeX-0-") else 0
        # Check ARM architecture
        is_arm = 1 if "arm64" in name_lower or "aarch64" in name_lower else 0
        arm_match = 1 if (is_arm == 1 and prefers_arm) or (is_arm == 0 and not prefers_arm) else 0
        return (tinytex1, tinytex, arm_match)
    
    compatible = []
    for asset in assets:
        name = asset.get("name", "")
        
        # Must end with correct suffix
        if not name.endswith(suffix):
            continue
        
        # Must start with TinyTeX-1 or TinyTeX (but not TinyTeX-0)
        if name.startswith("TinyTeX-1-") or (name.startswith("TinyTeX-") and not name.startswith("TinyTeX-0-")):
            url = asset.get("browser_download_url")
            if url:
                compatible.append((rank(name), asset))
    
    if not compatible:
        raise RuntimeError(f"Could not find compatible TinyTeX release for this platform (suffix: {suffix})")
    
    compatible.sort(key=lambda item: item[0], reverse=True)
    selected = compatible[0][1]
    archive_url = selected["browser_download_url"]
    archive_name = selected["name"]
    
    tinytex_dir = get_tinytex_cache_dir()
    tinytex_dir.mkdir(parents=True, exist_ok=True)
    
    with tempfile.TemporaryDirectory(prefix="epub2pdf_tinytex_") as temp_dir:
        archive_path = Path(temp_dir) / archive_name
        print(f"Downloading {archive_name}...")
        urllib.request.urlretrieve(archive_url, archive_path)
        
        print("Extracting TinyTeX...")
        if os.name == "nt":
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(tinytex_dir)
        else:
            with tarfile.open(archive_path, "r:gz") as archive:
                archive.extractall(tinytex_dir)
    
    print(f"TinyTeX installed to: {tinytex_dir}")


def ensure_xelatex_available() -> str:
    """Ensure xelatex is available, downloading TinyTeX if needed."""
    # Priority 1: Cache directory
    cached = find_xelatex_in_cache()
    if cached:
        return cached
    
    # Priority 2: TINYTEX_HOME environment variable
    tinytex_home = os.environ.get("TINYTEX_HOME")
    if tinytex_home:
        for candidate in get_tinytex_bin_candidates(Path(tinytex_home)):
            exe = candidate / ("xelatex.exe" if os.name == "nt" else "xelatex")
            if exe.exists():
                return str(exe.resolve())
    
    # Priority 3: System PATH
    system_xelatex = shutil.which("xelatex")
    if system_xelatex:
        return system_xelatex
    
    # Priority 4: Download TinyTeX
    print("xelatex not found. Installing TinyTeX...")
    download_tinytex()
    
    # Verify installation
    cached = find_xelatex_in_cache()
    if cached:
        return cached
    
    raise RuntimeError(
        "Failed to locate xelatex after TinyTeX installation. "
        "Please install TinyTeX manually and set TINYTEX_HOME environment variable."
    )


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

    # Ensure xelatex is available (download TinyTeX if needed)
    pdf_engine = ensure_xelatex_available()
    engine_name = Path(pdf_engine).stem.lower()
    
    # Restore original LD_LIBRARY_PATH to avoid conflicts with PyInstaller bundled libs
    env = dict(os.environ)
    if sys.platform.startswith("linux"):
        lp_key = "LD_LIBRARY_PATH"
        lp_orig = env.get(lp_key + "_ORIG")
        if lp_orig is not None:
            env[lp_key] = lp_orig
        else:
            env.pop(lp_key, None)

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
        
        # Use modified environment if needed (Linux LD_LIBRARY_PATH fix)
        if sys.platform.startswith("linux") and "env" in locals():
            pypandoc.convert_file(
                str(input_file),
                "pdf",
                outputfile=str(output_file),
                extra_args=scoped_args,
            )
        else:
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
