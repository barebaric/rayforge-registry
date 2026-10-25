#!/usr/bin/env python3
"""
Polls allowlisted addon repositories for new release tags.

For every repository in allowed-repositories.yaml, the highest
semantic version tag is compared against the versions already recorded
in registry.yaml. Unknown releases are validated and applied to
registry.yaml in place; a JSON summary is written so the calling
workflow can choose between a direct commit and a review pull request.
"""

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

import semver
import yaml

import update_registry
import validate_addon
from get_commit_mode import get_commit_mode

ALLOWLIST_FILE = Path("allowed-repositories.yaml")
TAGS_URL = "https://api.github.com/repos/{repo}/tags?per_page=100"
METADATA_URL = (
    "https://raw.githubusercontent.com/{repo}/{tag}/rayforge-addon.yaml"
)
TAG_PREFIX = "v"
MAX_PAGES = 10
REQUEST_TIMEOUT = 30

NEXT_LINK_RE = re.compile(r'<([^>]*)>;\s*rel="next"')


def parse_arguments() -> argparse.Namespace:
    """
    Parses command-line arguments for the script.

    Returns:
        argparse.Namespace: The parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Poll addon repositories for new release tags."
    )
    parser.add_argument(
        "--allowlist-file",
        type=Path,
        default=ALLOWLIST_FILE,
        help="Path to allowed-repositories.yaml.",
    )
    parser.add_argument(
        "--registry-file",
        type=Path,
        default=Path("registry.yaml"),
        help="Path to registry.yaml (updated in place).",
    )
    parser.add_argument(
        "--result-file",
        type=Path,
        default=Path("poll-result.json"),
        help="Path of the JSON summary for the calling workflow.",
    )
    return parser.parse_args()


def build_request(url: str, token: str = "") -> urllib.request.Request:
    """Creates a GitHub API request with the standard headers."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "rayforge-registry-poller",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.Request(url, headers=headers)


def next_page_url(link_header: Optional[str]) -> Optional[str]:
    """Extracts the rel='next' URL from a Link response header."""
    if not link_header:
        return None
    match = NEXT_LINK_RE.search(link_header)
    return match.group(1) if match else None


def fetch_tag_names(repo: str, token: str) -> List[str]:
    """
    Returns all tag names of the given repository.

    Raises OSError on network or HTTP errors.

    Args:
        repo: The repository name (e.g., 'owner/name').
        token: GitHub API token; empty for unauthenticated requests.

    Returns:
        A list of tag names.
    """
    names: List[str] = []
    url: Optional[str] = TAGS_URL.format(repo=repo)
    for _ in range(MAX_PAGES):
        if url is None:
            break
        request = build_request(url, token)
        with urllib.request.urlopen(
            request, timeout=REQUEST_TIMEOUT
        ) as response:
            data = json.load(response)
        if not isinstance(data, list):
            raise ValueError(f"Unexpected API response for {repo}.")
        names.extend(item["name"] for item in data)
        url = next_page_url(response.headers.get("Link"))
    return names


def latest_semver_tag(tag_names: List[str]) -> Optional[str]:
    """
    Returns the highest v-prefixed semantic version tag, if any.

    Args:
        tag_names: A list of git tag names.

    Returns:
        The tag name of the highest semantic version, or None if the
        repository has no semantic version tags.
    """
    versions = []
    for name in tag_names:
        if not name.startswith(TAG_PREFIX):
            continue
        try:
            version = semver.VersionInfo.parse(name[len(TAG_PREFIX):])
        except ValueError:
            continue
        versions.append((version, name))
    if not versions:
        return None
    return max(versions)[1]


def load_yaml_file(path: Path) -> Dict[str, Any]:
    """
    Loads and parses a YAML file.

    Raises FileNotFoundError if the file does not exist.
    """
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        return data if data is not None else {}


def known_versions(registry: Dict[str, Any], repo: str) -> set:
    """
    Returns all version tags the registry already lists for a repo.

    An addon is matched by its repository URL, so the result covers
    every registry entry that points at the given repository.
    """
    repository_url = f"https://github.com/{repo}"
    known = set()
    for addon in registry.get("addons", {}).values():
        if addon.get("repository") != repository_url:
            continue
        for entry in addon.get("versions", []):
            known.add(update_registry._get_version_tag(entry))
        known.add(str(addon.get("latest_stable", "")))
    known.discard("")
    return known


def download_metadata(repo: str, tag: str) -> Dict[str, Any]:
    """
    Downloads and parses rayforge-addon.yaml at the given tag.

    Raises OSError on network or HTTP errors, and ValueError if the
    metadata is not a YAML dictionary.
    """
    tag_path = urllib.parse.quote(tag, safe="")
    url = METADATA_URL.format(repo=repo, tag=tag_path)
    request = build_request(url)
    with urllib.request.urlopen(
        request, timeout=REQUEST_TIMEOUT
    ) as response:
        text = response.read().decode("utf-8")
    metadata = yaml.safe_load(text)
    if not isinstance(metadata, dict):
        raise ValueError("'rayforge-addon.yaml' must be a YAML dictionary.")
    return metadata


def poll_repository(
    repo: str, mode: str, registry: Dict[str, Any], token: str
) -> Dict[str, Any]:
    """
    Checks one repository and applies a new release to the registry.

    The registry dictionary is modified in place when a new release is
    found and validates successfully.

    Args:
        repo: The repository name (e.g., 'owner/name').
        mode: The commit mode ('direct' or 'pr').
        registry: The full, current registry data.
        token: GitHub API token; empty for unauthenticated requests.

    Returns:
        A result dictionary describing the outcome for this repository.
    """
    tag = ""
    try:
        tag = latest_semver_tag(fetch_tag_names(repo, token)) or ""
        if not tag:
            return {"repo": repo, "status": "skipped", "detail": "no tags"}
        if tag in known_versions(registry, repo):
            return {"repo": repo, "status": "up_to_date", "tag": tag}
        metadata = download_metadata(repo, tag)
        validate_addon.validate_schema(metadata)
        validate_addon.validate_content(metadata, tag=tag)
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        yaml.YAMLError,
    ) as e:
        return {
            "repo": repo,
            "status": "failed",
            "tag": tag,
            "error": str(e),
        }
    update_registry.update_addon_entry(registry, metadata, repo, tag)
    return {"repo": repo, "status": "updated", "tag": tag, "mode": mode}


def outcome_line(result: Dict[str, Any]) -> str:
    """Formats one poll result as a human-readable line."""
    repo = result["repo"]
    status = result["status"]
    tag = result.get("tag", "")
    if status == "updated":
        return f"{repo}@{tag}: published ({result['mode']})"
    if status == "failed":
        suffix = f"@{tag}" if tag else ""
        return f"{repo}{suffix}: FAILED - {result['error']}"
    if status == "up_to_date":
        return f"{repo}@{tag}: up to date"
    return f"{repo}: {result['detail']}"


def write_step_summary(results: List[Dict[str, Any]]) -> None:
    """Appends a markdown summary to the GitHub Actions step summary."""
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    lines = ["## Addon release poll", ""]
    for result in results:
        lines.append(f"- {outcome_line(result)}")
    with open(summary_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> int:
    """Main execution function for the script."""
    args = parse_arguments()
    allowlist = load_yaml_file(args.allowlist_file)
    registry = load_yaml_file(args.registry_file)
    token = os.environ.get("GITHUB_TOKEN", "")

    results = []
    seen = set()
    for item in allowlist.get("repositories", []):
        repo = item.get("repo", "")
        if not repo or repo in seen:
            continue
        seen.add(repo)
        mode = get_commit_mode(repo, allowlist)
        print(f"Checking {repo}...")
        results.append(poll_repository(repo, mode, registry, token))
    for result in results:
        print(outcome_line(result))

    updates = [r for r in results if r["status"] == "updated"]
    failures = [r for r in results if r["status"] == "failed"]
    if updates:
        update_registry.save_yaml_file(registry, args.registry_file)
    with open(args.result_file, "w", encoding="utf-8") as f:
        json.dump({"updates": updates, "failures": failures}, f, indent=2)
    write_step_summary(results)

    if failures:
        print(
            f"ERROR: {len(failures)} release(s) failed; the remaining "
            "releases were applied.",
            file=sys.stderr,
        )
        return 1
    print(f"Poll complete: {len(updates)} new release(s).")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, yaml.YAMLError) as e:
        print(f"ERROR: Release poll failed. {e}", file=sys.stderr)
        sys.exit(1)
