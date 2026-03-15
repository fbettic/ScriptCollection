#!/usr/bin/env python3
"""Quick test script to verify TinyTeX download logic works for all platforms."""

import json
import sys
import urllib.request


def test_download_logic():
    """Test that we can find TinyTeX releases for each platform."""
    
    api_url = "https://api.github.com/repos/rstudio/tinytex-releases/releases/latest"
    request = urllib.request.Request(
        api_url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "epub2pdf-test"},
    )
    
    print("Fetching latest TinyTeX release...")
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    
    assets = payload.get("assets", [])
    tag_name = payload.get("tag_name", "unknown")
    
    print(f"\nRelease: {tag_name}")
    print(f"Total assets: {len(assets)}\n")
    
    # Test each platform
    platforms_to_test = {
        "windows": ".zip",
        "linux": ".tar.gz",
        "macos": ".tar.gz",
    }
    
    results = {}
    
    for platform_name, suffix in platforms_to_test.items():
        print(f"Testing {platform_name}:")
        print(f"  Looking for: TinyTeX-1-*{suffix} or TinyTeX-*{suffix} (excluding TinyTeX-0-*, arm64)")
        
        matches = []
        for asset in assets:
            name = asset.get("name", "")
            name_lower = name.lower()
            
            if not name.endswith(suffix):
                continue
            
            # Prefer TinyTeX-1 but accept TinyTeX (excluding TinyTeX-0)
            if name.startswith("TinyTeX-1-") or (name.startswith("TinyTeX-") and not name.startswith("TinyTeX-0-")):
                # Skip arm64 for this test
                if "arm64" not in name_lower:
                    matches.append(name)
        
        if matches:
            print(f"  [PASS] Found {len(matches)} match(es):")
            for match in matches:
                print(f"     - {match}")
            results[platform_name] = True
        else:
            print(f"  [FAIL] No matches found!")
            results[platform_name] = False
        print()
    
    # Summary
    print("=" * 60)
    print("Summary:")
    all_pass = all(results.values())
    
    for platform, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {platform}: {status}")
    
    print("=" * 60)
    
    if all_pass:
        print("\n[OK] All platforms can download TinyTeX successfully!")
        return 0
    else:
        print("\n[FAIL] Some platforms failed. Check the logic above.")
        print("\nAvailable assets:")
        for asset in assets:
            print(f"  - {asset.get('name', 'unknown')}")
        return 1


if __name__ == "__main__":
    sys.exit(test_download_logic())
