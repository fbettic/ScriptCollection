#!/usr/bin/env python3
"""Download TinyTeX for specified platform to use in GitHub Actions releases."""

import argparse
import json
import platform
import sys
import urllib.request
from pathlib import Path


def get_platform_info():
    """Detect current platform and return appropriate TinyTeX suffix."""
    system = platform.system()
    machine = platform.machine().lower()
    
    if system == "Windows":
        return "windows", ".zip"
    elif system == "Darwin":
        return "macos", ".tar.gz"
    else:
        return "linux", ".tar.gz"


def download_tinytex(platform_name: str, output_dir: Path) -> Path:
    """Download TinyTeX for specified platform."""
    print(f"Fetching TinyTeX releases for {platform_name}...")
    
    api_url = "https://api.github.com/repos/rstudio/tinytex-releases/releases/latest"
    request = urllib.request.Request(
        api_url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "epub2pdf-builder"},
    )
    
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"Error fetching TinyTeX releases: {e}", file=sys.stderr)
        sys.exit(1)
    
    assets = payload.get("assets", [])
    tag_name = payload.get("tag_name", "unknown")
    
    # Find appropriate asset for platform
    platform_map = {
        "windows": (".zip", "windows"),
        "linux": (".tar.gz", "linux"),
        "macos": (".tar.gz", "darwin"),
    }
    
    if platform_name not in platform_map:
        print(f"Unknown platform: {platform_name}", file=sys.stderr)
        sys.exit(1)
    
    suffix, keyword = platform_map[platform_name]
    
    candidates = []
    for asset in assets:
        name = asset.get("name", "")
        if not name.endswith(suffix):
            continue
        if keyword not in name.lower():
            continue
        if name.startswith("TinyTeX-1-") or name.startswith("TinyTeX-"):
            candidates.append(asset)
    
    if not candidates:
        print(f"No TinyTeX release found for {platform_name}", file=sys.stderr)
        sys.exit(1)
    
    # Prefer TinyTeX-1 (minimal version)
    selected = None
    for candidate in candidates:
        if candidate["name"].startswith("TinyTeX-1-"):
            selected = candidate
            break
    
    if not selected:
        selected = candidates[0]
    
    download_url = selected["browser_download_url"]
    filename = selected["name"]
    output_path = output_dir / filename
    
    print(f"Downloading {filename} from {tag_name}...")
    print(f"URL: {download_url}")
    
    try:
        urllib.request.urlretrieve(download_url, output_path)
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"✓ Downloaded: {output_path} ({file_size_mb:.1f} MB)")
        return output_path
    except Exception as e:
        print(f"Error downloading TinyTeX: {e}", file=sys.stderr)
        if output_path.exists():
            output_path.unlink()
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Download TinyTeX for release packaging")
    parser.add_argument(
        "--platform",
        choices=["windows", "linux", "macos"],
        help="Target platform (auto-detect if omitted)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.cwd(),
        help="Output directory (default: current directory)",
    )
    
    args = parser.parse_args()
    
    if args.platform:
        platform_name = args.platform
    else:
        platform_name, _ = get_platform_info()
        print(f"Auto-detected platform: {platform_name}")
    
    args.output.mkdir(parents=True, exist_ok=True)
    
    output_path = download_tinytex(platform_name, args.output)
    print(f"\n✓ TinyTeX ready for release: {output_path}")


if __name__ == "__main__":
    main()
