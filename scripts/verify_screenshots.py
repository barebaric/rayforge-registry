#!/usr/bin/env python3
"""
Verifies that an addon's declared screenshots are fetchable.

Each screenshot path from rayforge-addon.yaml is resolved to a raw
GitHub URL at the release tag and downloaded over plain HTTPS. The
release is rejected if any screenshot is missing, is not an image, or
exceeds the size limit. No git checkout is required.
"""

import argparse
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict

import yaml

import update_registry

MAX_SCREENSHOT_BYTES = 3 * 1024 * 1024
REQUEST_TIMEOUT = 30
USER_AGENT = "rayforge-registry-poller"


def verify_screenshots(repo: str, tag: str, metadata: Dict[str, Any]) -> None:
    """
    Downloads every declared screenshot and checks its response.

    Raises ValueError if a screenshot is not an image or too large,
    and OSError on network or HTTP errors.
    """
    for path in metadata.get("screenshots") or []:
        url = update_registry.resolve_screenshot_url(repo, tag, path)
        request = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT}
        )
        with urllib.request.urlopen(
            request, timeout=REQUEST_TIMEOUT
        ) as response:
            content_type = response.headers.get("Content-Type", "")
            data = response.read(MAX_SCREENSHOT_BYTES + 1)
        if not content_type.startswith("image/"):
            raise ValueError(
                f"Screenshot '{path}' is not an image "
                f"(Content-Type: {content_type})."
            )
        if len(data) > MAX_SCREENSHOT_BYTES:
            raise ValueError(
                f"Screenshot '{path}' exceeds the "
                f"{MAX_SCREENSHOT_BYTES} byte size limit."
            )
        print(f"   ... Screenshot '{path}' OK ({len(data)} bytes)")


def main() -> int:
    """Main execution function for the script."""
    parser = argparse.ArgumentParser(
        description="Verify an addon's screenshots at a release tag."
    )
    parser.add_argument(
        "metadata_file",
        type=Path,
        help="Path to the rayforge-addon.yaml file.",
    )
    parser.add_argument(
        "--repo", required=True, help="Repository name (owner/repo)"
    )
    parser.add_argument(
        "--tag", required=True, help="Git tag of the release"
    )
    args = parser.parse_args()

    try:
        with open(args.metadata_file, "r", encoding="utf-8") as f:
            metadata = yaml.safe_load(f)
        if not isinstance(metadata, dict):
            raise ValueError("Metadata must be a YAML dictionary.")
        print(f"-> Verifying screenshots for {args.repo}@{args.tag}...")
        verify_screenshots(args.repo, args.tag, metadata)
        print("   ... Screenshots OK")
        return 0
    except (OSError, ValueError, yaml.YAMLError) as e:
        print(f"ERROR: Screenshot verification failed. {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())