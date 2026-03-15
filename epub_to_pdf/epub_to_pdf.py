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


def find_pdf_engine() -> str | None:
    """Return the first available PDF engine executable supported by pandoc."""
    for engine in ("pdflatex", "xelatex", "lualatex", "tectonic"):
        path = shutil.which(engine)
        if path:
            return path
    return None


def ensure_pdf_engine_available() -> str:
    """Ensure a LaTeX engine is available to generate PDF output."""
    existing_engine = find_pdf_engine()
    if existing_engine:
        return existing_engine

    return ensure_tectonic_available()


def resolve_output_path(input_file: Path, output_file: str | None) -> Path:
    """Resolve output path using input path when output is omitted."""
    if output_file:
        return Path(output_file).expanduser().resolve()
    return input_file.with_suffix(".pdf")


def convert_epub_to_pdf(input_file: Path, output_file: Path) -> None:
    """Convert one EPUB file to PDF."""
    if not input_file.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_file}")
    if input_file.suffix.lower() != ".epub":
        raise ValueError(f"Input file must be an EPUB: {input_file}")

    pypandoc = ensure_python_dependency("pypandoc")
    ensure_python_dependency("ebooklib", "EbookLib")
    ensure_pandoc_available(pypandoc)
    pdf_engine = ensure_pdf_engine_available()

    output_file.parent.mkdir(parents=True, exist_ok=True)
    pypandoc.convert_file(
        str(input_file),
        "pdf",
        outputfile=str(output_file),
        extra_args=[f"--pdf-engine={pdf_engine}"],
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
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.input_file).expanduser().resolve()
    output_path = resolve_output_path(input_path, args.output_file)

    try:
        convert_epub_to_pdf(input_path, output_path)
    except Exception as exc:  # pragma: no cover
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"PDF generated successfully: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
