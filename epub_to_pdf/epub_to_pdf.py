#!/usr/bin/env python3
"""CLI utility to convert EPUB files to PDF using pypandoc."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
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

PROFILE_PRESETS: dict[str, dict[str, str | int | None]] = {
    "fiction": {
        "margin": "12mm",
        "mainfont": None,
        "dpi": 180,
        "pdf_engine": None,
        "font_mode": "auto",
        "text_layout": "adaptive",
        "image_layout": "contain",
    },
    "math": {
        "margin": "25mm",
        "mainfont": "Noto Serif",
        "dpi": 300,
        "pdf_engine": "xelatex",
        "font_mode": "local",
        "text_layout": "adaptive",
        "image_layout": "contain",
    },
    "biology": {
        "margin": "10mm",
        "mainfont": "Noto Serif",
        "dpi": 300,
        "pdf_engine": "xelatex",
        "font_mode": "local",
        "text_layout": "adaptive",
        "image_layout": "contain",
    },
}


def get_local_fonts_dir() -> Path:
    """Return local directory used to store managed font files."""
    return Path(__file__).resolve().parent / "fonts"


def ensure_local_fonts_available(fonts_dir: Path | None = None) -> Path:
    """Ensure required local fonts exist in script folder (download if needed)."""
    target_dir = fonts_dir or get_local_fonts_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    for filename, url in LOCAL_FONT_FILES.items():
        path = target_dir / filename
        if not path.exists():
            print(f"Font '{filename}' not found. Downloading...", file=sys.stderr)
            download_file(url, path)

    return target_dir


def build_latex_layout_header(
    text_layout: str,
    image_layout: str,
    engine_name: str,
    mainfont: str | None,
    font_mode: str,
    fonts_dir: Path | None = None,
) -> str:
    """Build LaTeX header directives for text and image layout tuning."""
    lines: list[str] = []

    if engine_name in ("xelatex", "lualatex"):
        local_font_dir: Path | None = None
        if font_mode == "local":
            local_font_dir = ensure_local_fonts_available(fonts_dir)
        elif font_mode == "auto":
            candidate_dir = fonts_dir or get_local_fonts_dir()
            if any((candidate_dir / name).exists() for name in LOCAL_FONT_FILES):
                local_font_dir = ensure_local_fonts_available(candidate_dir)

        if local_font_dir is not None:
            latex_path = local_font_dir.as_posix()
            lines.extend(
                [
                    r"\usepackage{fontspec}",
                    r"\usepackage{unicode-math}",
                    r"\defaultfontfeatures{Ligatures=TeX}",
                    rf"\setmainfont[Path={{{latex_path}/}},Extension=.ttf,UprightFont=*-Regular,BoldFont=*-Bold,ItalicFont=*-Italic,BoldItalicFont=*-BoldItalic]{{NotoSerif}}",
                    rf"\setmathfont[Path={{{latex_path}/}}]{{NotoSansMath-Regular.ttf}}",
                ]
            )
        elif mainfont:
            lines.extend(
                [
                    r"\usepackage{fontspec}",
                    r"\defaultfontfeatures{Ligatures=TeX}",
                    rf"\setmainfont{{{mainfont}}}",
                ]
            )
    elif engine_name == "pdflatex":
        # Fallback for pdflatex where Unicode glyph coverage is limited by default fonts.
        lines.extend(
            [
                r"\usepackage[T1]{fontenc}",
                r"\usepackage[utf8]{inputenc}",
                r"\usepackage{textcomp}",
                r"\DeclareUnicodeCharacter{03C0}{\ensuremath{\pi}}",
                r"\DeclareUnicodeCharacter{03C6}{\ensuremath{\phi}}",
                r"\DeclareUnicodeCharacter{03A6}{\ensuremath{\Phi}}",
                r"\DeclareUnicodeCharacter{03BC}{\ensuremath{\mu}}",
                r"\DeclareUnicodeCharacter{0394}{\ensuremath{\Delta}}",
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
                # Reduce overfull/underfull warnings by allowing a bit more stretch.
                r"\setlength{\emergencystretch}{5em}",
                r"\tolerance=1800",
                r"\hbadness=2500",
                r"\hfuzz=1pt",
                r"\vfuzz=1pt",
                r"\sloppy",
            ]
        )

    return "\n".join(lines)


def ensure_python_dependency(import_name: str, pip_name: str | None = None):
    """Import a dependency or install it on the fly when running standalone."""
    package_name = pip_name or import_name
    try:
        return importlib.import_module(import_name)
    except ModuleNotFoundError:
        print(f"Dependency '{package_name}' not found. Installing...", file=sys.stderr)
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        return importlib.import_module(import_name)


def ensure_pandoc_available(pypandoc_module) -> None:
    """Download pandoc automatically if it is missing from the system."""
    try:
        pypandoc_module.get_pandoc_path()
    except OSError:
        print("Pandoc not found. Downloading pandoc binary...", file=sys.stderr)
        pypandoc_module.download_pandoc()


def get_local_bin_dir() -> Path:
    """Return a user-writable local bin directory for managed tools."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    return base / "epub_to_pdf" / "bin"


def get_local_tinytex_dir() -> Path:
    """Return local install directory for TinyTeX managed by this script."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    return base / "epub_to_pdf" / "tinytex"


def tinytex_bin_candidates(tinytex_dir: Path) -> list[Path]:
    """Return likely TinyTeX bin directories for current platform."""
    if os.name == "nt":
        return [
            tinytex_dir / "bin" / "windows",
            tinytex_dir / "bin" / "win32",
            tinytex_dir / "bin" / "win64",
        ]
    if sys.platform == "darwin":
        return [
            tinytex_dir / "bin" / "universal-darwin",
            tinytex_dir / "bin" / "x86_64-darwin",
            tinytex_dir / "bin" / "arm64-darwin",
        ]
    return [
        tinytex_dir / "bin" / "x86_64-linux",
        tinytex_dir / "bin" / "aarch64-linux",
    ]


def add_tinytex_to_path(tinytex_dir: Path) -> None:
    """Add TinyTeX bin directories to PATH for current process."""
    executable_names = ["xelatex", "lualatex", "pdflatex"]
    for engine in executable_names:
        filename = f"{engine}.exe" if os.name == "nt" else engine
        for path in tinytex_dir.rglob(filename):
            add_to_path(path.parent)
    for candidate in tinytex_bin_candidates(tinytex_dir):
        if candidate.exists():
            add_to_path(candidate)


def find_engine_in_tinytex(tinytex_dir: Path, engine: str) -> str | None:
    """Find an engine executable inside TinyTeX install directory."""
    executable_name = f"{engine}.exe" if os.name == "nt" else engine
    for candidate in tinytex_bin_candidates(tinytex_dir):
        engine_path = candidate / executable_name
        if engine_path.exists():
            return str(engine_path.resolve())
    for path in tinytex_dir.rglob(executable_name):
        return str(path.resolve())
    return None


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
    elif sys.platform == "darwin":
        suffix = ".tar.gz"
        prefers_arm = machine in ("arm64", "aarch64")
    else:
        suffix = ".tar.gz"
        prefers_arm = machine in ("arm64", "aarch64")

    def rank(name: str) -> tuple[int, int, int]:
        # Prioritize TinyTeX-1 then TinyTeX, and architecture match.
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


def ensure_tinytex_available(preferred_engine: str | None = None) -> str | None:
    """Install TinyTeX headlessly if needed and return an available engine path."""
    desired = preferred_engine if preferred_engine in ("xelatex", "lualatex", "pdflatex") else "xelatex"
    tinytex_dir = get_local_tinytex_dir()

    if tinytex_dir.exists():
        add_tinytex_to_path(tinytex_dir)
        existing = find_engine_in_tinytex(tinytex_dir, desired)
        if existing:
            return existing
        for fallback in ("xelatex", "lualatex", "pdflatex"):
            existing = find_engine_in_tinytex(tinytex_dir, fallback)
            if existing:
                return existing

    print("No Unicode LaTeX engine found. Downloading TinyTeX (headless)...", file=sys.stderr)
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
    preferred = find_engine_in_tinytex(tinytex_dir, desired)
    if preferred:
        return preferred
    for fallback in ("xelatex", "lualatex", "pdflatex"):
        candidate = find_engine_in_tinytex(tinytex_dir, fallback)
        if candidate:
            return candidate
    return None


def add_to_path(directory: Path) -> None:
    """Prepend directory to PATH for current process if not already present."""
    parts = os.environ.get("PATH", "").split(os.pathsep)
    as_text = str(directory)
    if as_text not in parts:
        os.environ["PATH"] = f"{as_text}{os.pathsep}{os.environ.get('PATH', '')}"


def platform_asset_hints() -> tuple[str, ...]:
    """Return filename hints used to pick the right tectonic release asset."""
    machine = platform.machine().lower()
    if sys.platform.startswith("win"):
        if machine in ("amd64", "x86_64"):
            return ("x86_64-pc-windows-msvc", ".zip")
        if machine in ("arm64", "aarch64"):
            return ("aarch64-pc-windows-msvc", ".zip")
    elif sys.platform == "darwin":
        if machine in ("arm64", "aarch64"):
            return ("aarch64-apple-darwin", ".tar.gz")
        return ("x86_64-apple-darwin", ".tar.gz")
    else:
        if machine in ("arm64", "aarch64"):
            return ("aarch64-unknown-linux-gnu", ".tar.gz")
        return ("x86_64-unknown-linux-gnu", ".tar.gz")

    raise RuntimeError(f"Unsupported platform/architecture: {sys.platform} {machine}")


def download_file(url: str, destination: Path) -> None:
    """Download URL to destination path."""
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


def query_latest_tectonic_asset_url() -> tuple[str, str]:
    """Get download URL and file name for the current platform from GitHub releases."""
    hints = platform_asset_hints()
    api_url = "https://api.github.com/repos/tectonic-typesetting/tectonic/releases/latest"
    request = urllib.request.Request(
        api_url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "epub-to-pdf-cli"},
    )
    with urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT_SECONDS) as response:
        payload = json.loads(response.read().decode("utf-8"))

    assets = payload.get("assets", [])
    for asset in assets:
        name = asset.get("name", "")
        if all(h in name for h in hints):
            url = asset.get("browser_download_url")
            if not url:
                continue
            return url, name

    raise RuntimeError("Could not find a compatible tectonic release asset for this OS.")


def extract_tectonic_binary(archive_path: Path, target_path: Path) -> None:
    """Extract tectonic executable from a zip or tar.gz archive."""
    expected_name = "tectonic.exe" if os.name == "nt" else "tectonic"

    if archive_path.suffix == ".zip":
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.namelist():
                if member.endswith("/" + expected_name) or member == expected_name:
                    with archive.open(member) as source, target_path.open("wb") as output:
                        shutil.copyfileobj(source, output)
                    break
            else:
                raise RuntimeError("Tectonic executable not found in downloaded zip.")
    else:
        with tarfile.open(archive_path, "r:gz") as archive:
            for member in archive.getmembers():
                if member.name.endswith("/" + expected_name) or member.name == expected_name:
                    extracted = archive.extractfile(member)
                    if extracted is None:
                        continue
                    with extracted, target_path.open("wb") as output:
                        shutil.copyfileobj(extracted, output)
                    break
            else:
                raise RuntimeError("Tectonic executable not found in downloaded tar.gz.")

    if os.name != "nt":
        target_path.chmod(target_path.stat().st_mode | stat.S_IXUSR)


def ensure_tectonic_available() -> str:
    """Ensure a non-interactive PDF engine exists by managing tectonic locally."""
    existing = shutil.which("tectonic")
    if existing:
        return existing

    bin_dir = get_local_bin_dir()
    bin_dir.mkdir(parents=True, exist_ok=True)
    executable = bin_dir / ("tectonic.exe" if os.name == "nt" else "tectonic")
    if executable.exists():
        add_to_path(bin_dir)
        return str(executable.resolve())

    print("No PDF engine found. Downloading tectonic (headless)...", file=sys.stderr)
    asset_url, asset_name = query_latest_tectonic_asset_url()
    with tempfile.TemporaryDirectory(prefix="epub_to_pdf_") as temp_dir:
        archive_path = Path(temp_dir) / asset_name
        download_file(asset_url, archive_path)
        extract_tectonic_binary(archive_path, executable)

    add_to_path(bin_dir)
    if executable.exists():
        return str(executable.resolve())
    raise RuntimeError("Tectonic was downloaded but is not executable in this environment.")


def find_pdf_engine(preferred_engine: str | None = None) -> str | None:
    """Return the first available PDF engine executable supported by pandoc."""
    candidates: tuple[str, ...]
    if preferred_engine:
        candidates = (preferred_engine,)
    else:
        # Prefer Unicode-capable engines to reduce missing glyph warnings.
        candidates = ("xelatex", "lualatex", "tectonic", "pdflatex")

    for engine in candidates:
        path = shutil.which(engine)
        if path:
            return path
    return None


def ensure_pdf_engine_available(preferred_engine: str | None = None, strict: bool = False) -> str:
    """Ensure a LaTeX engine is available to generate PDF output."""
    existing_engine = find_pdf_engine(preferred_engine)
    if existing_engine:
        return existing_engine

    if preferred_engine in ("xelatex", "lualatex", "pdflatex") or preferred_engine is None:
        tinytex_engine = ensure_tinytex_available(preferred_engine)
        if tinytex_engine:
            print(f"Using TinyTeX engine '{Path(tinytex_engine).stem}'.", file=sys.stderr)
            return tinytex_engine

    if preferred_engine == "tectonic":
        return ensure_tectonic_available()

    if preferred_engine:
        # If preferred engine is missing, fallback to any available one.
        fallback_engine = find_pdf_engine()
        if fallback_engine:
            print(
                f"Preferred engine '{preferred_engine}' not found. Using '{Path(fallback_engine).stem}' instead.",
                file=sys.stderr,
            )
            return fallback_engine

        # No engine found in PATH: auto-provision tectonic.
        print(
            f"Preferred engine '{preferred_engine}' not found. Auto-provisioning 'tectonic'.",
            file=sys.stderr,
        )
        return ensure_tectonic_available()

    return ensure_tectonic_available()


def resolve_output_path(input_file: Path, output_file: str | None) -> Path:
    """Resolve output path using input path when output is omitted."""
    if output_file:
        return Path(output_file).expanduser().resolve()
    return input_file.with_suffix(".pdf")


def convert_epub_to_pdf(
    input_file: Path,
    output_file: Path,
    margin: str = "18mm",
    preferred_engine: str | None = None,
    mainfont: str | None = None,
    dpi: int | None = None,
    text_layout: str = "adaptive",
    image_layout: str = "contain",
    font_mode: str = "auto",
    fonts_dir: Path | None = None,
    strict_engine: bool = False,
) -> None:
    """Convert one EPUB file to PDF."""
    if not input_file.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_file}")
    if input_file.suffix.lower() != ".epub":
        raise ValueError(f"Input file must be an EPUB: {input_file}")

    pypandoc = ensure_python_dependency("pypandoc")
    ensure_python_dependency("ebooklib", "EbookLib")
    ensure_pandoc_available(pypandoc)
    pdf_engine = ensure_pdf_engine_available(preferred_engine, strict=strict_engine)
    engine_name = Path(pdf_engine).stem.lower()

    extra_args = [f"--pdf-engine={pdf_engine}", "-V", f"geometry:margin={margin}"]
    if mainfont and engine_name in ("xelatex", "lualatex") and font_mode == "system":
        extra_args.extend(["-V", f"mainfont={mainfont}"])
    if dpi is not None:
        extra_args.append(f"--dpi={dpi}")

    header = build_latex_layout_header(
        text_layout=text_layout,
        image_layout=image_layout,
        engine_name=engine_name,
        mainfont=mainfont,
        font_mode=font_mode,
        fonts_dir=fonts_dir,
    )
    if header:
        with tempfile.TemporaryDirectory(prefix="epub_to_pdf_header_") as temp_dir:
            header_file = Path(temp_dir) / "layout.tex"
            header_file.write_text(header, encoding="utf-8")
            scoped_args = [*extra_args, "--include-in-header", str(header_file)]

            output_file.parent.mkdir(parents=True, exist_ok=True)
            pypandoc.convert_file(
                str(input_file),
                "pdf",
                outputfile=str(output_file),
                extra_args=scoped_args,
            )
        return

    output_file.parent.mkdir(parents=True, exist_ok=True)
    pypandoc.convert_file(
        str(input_file),
        "pdf",
        outputfile=str(output_file),
        extra_args=extra_args,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert an EPUB file to PDF using pandoc."
    )
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
        "--pdf-engine",
        choices=["xelatex", "lualatex", "tectonic", "pdflatex"],
        help="Optional PDF engine to force. By default, the script prefers xelatex/lualatex.",
    )
    parser.add_argument(
        "--mainfont",
        help="Optional main font name (useful for xelatex/lualatex, e.g. 'Noto Serif').",
    )
    parser.add_argument(
        "--font-mode",
        choices=["auto", "local", "system"],
        help="Font source strategy for xelatex/lualatex: auto, local (script/fonts), or system.",
    )
    parser.add_argument(
        "--fonts-dir",
        help="Optional folder path containing TTF fonts for local mode.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        help="Image DPI hint for pandoc (useful for image-heavy books).",
    )
    parser.add_argument(
        "--text-layout",
        choices=["adaptive", "standard"],
        help="Text line-breaking strategy. 'adaptive' reduces overfull/underfull warnings.",
    )
    parser.add_argument(
        "--image-layout",
        choices=["contain", "standard"],
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
    mainfont_value = args.mainfont if args.mainfont is not None else selected_profile.get("mainfont")
    mainfont = str(mainfont_value).strip() if isinstance(mainfont_value, str) else None
    font_mode_value = args.font_mode if args.font_mode is not None else selected_profile.get("font_mode", "auto")
    font_mode = str(font_mode_value).strip()
    fonts_dir = Path(args.fonts_dir).expanduser().resolve() if args.fonts_dir else None
    dpi_value = args.dpi if args.dpi is not None else selected_profile.get("dpi")
    dpi = int(dpi_value) if isinstance(dpi_value, int) else None
    engine_value = args.pdf_engine if args.pdf_engine is not None else selected_profile.get("pdf_engine")
    preferred_engine = str(engine_value) if isinstance(engine_value, str) else None
    strict_engine = args.pdf_engine is not None
    text_layout_value = args.text_layout if args.text_layout is not None else selected_profile.get(
        "text_layout", "adaptive"
    )
    text_layout = str(text_layout_value).strip()
    image_layout_value = args.image_layout if args.image_layout is not None else selected_profile.get(
        "image_layout", "contain"
    )
    image_layout = str(image_layout_value).strip()

    if not margin:
        print("Error: --margin cannot be empty.", file=sys.stderr)
        return 1

    if dpi is not None and dpi <= 0:
        print("Error: --dpi must be greater than 0.", file=sys.stderr)
        return 1

    if font_mode not in ("auto", "local", "system"):
        print("Error: --font-mode must be 'auto', 'local' or 'system'.", file=sys.stderr)
        return 1

    if text_layout not in ("adaptive", "standard"):
        print("Error: --text-layout must be 'adaptive' or 'standard'.", file=sys.stderr)
        return 1

    if image_layout not in ("contain", "standard"):
        print("Error: --image-layout must be 'contain' or 'standard'.", file=sys.stderr)
        return 1

    try:
        convert_epub_to_pdf(
            input_path,
            output_path,
            margin=margin,
            preferred_engine=preferred_engine,
            mainfont=mainfont,
            font_mode=font_mode,
            fonts_dir=fonts_dir,
            dpi=dpi,
            text_layout=text_layout,
            image_layout=image_layout,
            strict_engine=strict_engine,
        )
    except Exception as exc:  # pragma: no cover
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"PDF generated successfully: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
