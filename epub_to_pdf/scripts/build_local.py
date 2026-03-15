#!/usr/bin/env python3
"""Local build script for testing PyInstaller packaging."""

import shutil
import subprocess
import sys
from pathlib import Path


def check_dependencies():
    """Verify required dependencies are installed."""
    missing = []
    
    try:
        import PyInstaller
    except ImportError:
        missing.append("pyinstaller")
    
    try:
        import pypandoc
    except ImportError:
        missing.append("pypandoc")
    
    if missing:
        print(f"Missing dependencies: {', '.join(missing)}")
        print(f"Install with: pip install {' '.join(missing)}")
        sys.exit(1)
    
    print("[OK] Dependencies check passed")


def clean_build_artifacts():
    """Remove previous build artifacts."""
    artifacts = ["build", "dist", "__pycache__"]
    for artifact in artifacts:
        path = Path(artifact)
        if path.exists():
            print(f"Cleaning {artifact}/")
            shutil.rmtree(path)


def build_executable():
    """Build executable with PyInstaller."""
    print("\nBuilding executable with PyInstaller...")
    
    spec_file = Path("epub_to_pdf.spec")
    if not spec_file.exists():
        print(f"Error: {spec_file} not found")
        sys.exit(1)
    
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(spec_file),
        "--noconfirm",
        "--log-level=WARN",
    ]
    
    try:
        result = subprocess.run(cmd, check=True)
        print("\n[OK] Build completed successfully")
    except subprocess.CalledProcessError as e:
        print(f"\n[FAIL] Build failed with exit code {e.returncode}")
        sys.exit(1)


def show_output_info():
    """Display information about the built executable."""
    dist_dir = Path("dist")
    if not dist_dir.exists():
        print("Warning: dist/ directory not found")
        return
    
    exe_name = "epub2pdf.exe" if sys.platform == "win32" else "epub2pdf"
    exe_path = dist_dir / exe_name
    
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\n[OK] Executable created: {exe_path}")
        print(f"  Size: {size_mb:.1f} MB")
        print(f"\nTest with:")
        print(f'  {exe_path} "path/to/file.epub"')
    else:
        print(f"\nWarning: Expected executable not found: {exe_path}")
        print(f"Contents of dist/:")
        for item in dist_dir.iterdir():
            print(f"  - {item.name}")


def main():
    print("epub2pdf Local Build Script")
    print("=" * 50)
    
    # Change to script's directory
    script_dir = Path(__file__).parent.parent
    if script_dir.exists():
        print(f"Working directory: {script_dir}")
        import os
        os.chdir(script_dir)
    
    check_dependencies()
    clean_build_artifacts()
    build_executable()
    show_output_info()
    
    print("\n" + "=" * 50)
    print("Build process completed!")


if __name__ == "__main__":
    main()
