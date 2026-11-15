#!/usr/bin/env python3
"""
Validates the registry for continuous integration.

Checks the structure of registry.yaml, verifies that every addon
repository is on the allowlist, and re-validates any releases that
were added or changed relative to a base registry file.
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import semver
import yaml

import poll_releases
import update_registry
import validate_addon
import verify_screenshots

REGISTRY_FILE = Path("registry.yaml")
ALLOWLIST_FILE = Path("allowed-repositories.yaml")
REPOSITORY_URL_PREFIX = "https://github.com/"
RAW_URL_PREFIX = "https://raw.githubusercontent.com/"
TAG_PREFIX = "v"


def parse_arguments() -> argparse.Namespace:
    """Parses command-line arguments for the script."""
    parser = argparse.ArgumentParser(
        description="Validate the registry for continuous integration."
    )
    parser.add_argument(
        "--registry-file",
        type=Path,
        default=REGISTRY_FILE,
        help="Path to registry.yaml.",
    )
    parser.add_argument(
        "--allowlist-file",
        type=Path,
        default=ALLOWLIST_FILE,
        help="Path to allowed-repositories.yaml.",
    )
    parser.add_argument(
        "--base-file",
        type=Path,
        default=None,
        help="Base registry to diff against. Added or changed releases "
        "are downloaded and re-validated.",
    )
    return parser.parse_args()


def repository_name(repository_url: str) -> str:
    """Extracts 'owner/repo' from a GitHub repository URL."""
    if not repository_url.startswith(REPOSITORY_URL_PREFIX):
        raise ValueError(
            f"Repository URL '{repository_url}' is not a GitHub URL."
        )
    return repository_url[len(REPOSITORY_URL_PREFIX):]


def _check_versions(name: str, entry: Dict[str, Any]) -> None:
    """Validates the version list of one addon entry."""
    versions = entry.get("versions")
    if not isinstance(versions, list) or not versions:
        raise ValueError(f"Addon '{name}' must list at least one version.")

    parsed = []
    seen = set()
    for item in versions:
        if not isinstance(item, dict):
            raise ValueError(
                f"Addon '{name}' has a malformed version entry: {item}"
            )
        tag = item.get("version", "")
        if not tag.startswith(TAG_PREFIX):
            raise ValueError(
                f"Addon '{name}' version '{tag}' must start with 'v'."
            )
        if tag in seen:
            raise ValueError(f"Addon '{name}' lists '{tag}' twice.")
        seen.add(tag)
        try:
            parsed.append(semver.VersionInfo.parse(tag[len(TAG_PREFIX):]))
        except ValueError:
            raise ValueError(
                f"Addon '{name}' version '{tag}' is not a valid "
                "semantic version."
            )
        api_version = item.get("api_version")
        if not isinstance(api_version, int) or api_version < 1:
            raise ValueError(
                f"Addon '{name}' version '{tag}' needs a positive "
                "integer api_version."
            )

    if parsed != sorted(parsed, reverse=True):
        raise ValueError(
            f"Addon '{name}' versions are not sorted newest first."
        )
    if entry.get("latest_stable") != versions[0].get("version"):
        raise ValueError(
            f"Addon '{name}' latest_stable does not match its newest "
            "version."
        )


def _check_license(name: str, license_data: Any) -> None:
    """Validates the optional license section of an addon entry."""
    if license_data is None:
        return
    if not isinstance(license_data, dict):
        raise ValueError(f"Addon '{name}' license must be a dictionary.")
    license_name = license_data.get("name")
    if not isinstance(license_name, str) or not license_name.strip():
        raise ValueError(
            f"Addon '{name}' needs a non-empty 'license.name'."
        )


def _check_screenshots(name: str, screenshots: Any) -> None:
    """Validates the optional screenshot URLs of an addon entry."""
    if not screenshots:
        return
    if not isinstance(screenshots, list):
        raise ValueError(f"Addon '{name}' screenshots must be a list.")
    for url in screenshots:
        if not isinstance(url, str) or not url.startswith(RAW_URL_PREFIX):
            raise ValueError(
                f"Addon '{name}' screenshot '{url}' must be a raw "
                "GitHub URL pinned to a release tag."
            )


def _check_addon_entry(
    name: str, entry: Dict[str, Any], allowed: set
) -> None:
    """Validates the structure of one addon entry."""
    if not name.isidentifier():
        raise ValueError(f"Addon name '{name}' is not a valid identifier.")
    if not isinstance(entry, dict):
        raise ValueError(f"Addon '{name}' must be a dictionary.")

    for key in ("display_name", "description"):
        value = entry.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Addon '{name}' needs a non-empty '{key}'.")

    api_version = entry.get("api_version")
    if not isinstance(api_version, int) or api_version < 1:
        raise ValueError(
            f"Addon '{name}' needs a positive integer api_version."
        )

    author = entry.get("author")
    if not isinstance(author, dict):
        raise ValueError(f"Addon '{name}' needs an 'author' dictionary.")
    for key in ("name", "email"):
        value = author.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"Addon '{name}' needs a non-empty 'author.{key}'."
            )

    repository_url = entry.get("repository")
    if not isinstance(repository_url, str) or not repository_url:
        raise ValueError(f"Addon '{name}' needs a 'repository' URL.")
    repo = repository_name(repository_url)
    if repo not in allowed:
        raise ValueError(
            f"Addon '{name}' repository '{repo}' is not on the allowlist."
        )

    validate_addon._check_depends(entry.get("depends", []))
    _check_license(name, entry.get("license"))
    _check_screenshots(name, entry.get("screenshots", []))
    _check_versions(name, entry)


def validate_structure(
    registry: Dict[str, Any], allowlist: Dict[str, Any]
) -> None:
    """Validates every addon entry and its allowlist authorization."""
    addons = registry.get("addons")
    if not isinstance(addons, dict) or not addons:
        raise ValueError("Registry must contain a non-empty 'addons' map.")
    allowed = {
        item.get("repo")
        for item in allowlist.get("repositories", [])
        if item.get("repo")
    }
    for name, entry in addons.items():
        _check_addon_entry(name, entry, allowed)
    print(f"   ... {len(addons)} addon entries OK")


def changed_releases(
    registry: Dict[str, Any], base: Dict[str, Any]
) -> List[Tuple[str, str, str]]:
    """
    Returns (repo, tag, addon name) triples for added or changed versions.

    A version counts as changed when it is missing from the base
    registry or its api_version differs.
    """
    base_versions = {}
    for name, entry in (base.get("addons") or {}).items():
        for item in entry.get("versions") or []:
            parsed = update_registry._parse_version_entry(item)
            base_versions[(name, parsed["version"])] = parsed["api_version"]

    changed = []
    for name, entry in registry.get("addons", {}).items():
        repo = repository_name(entry.get("repository", ""))
        for item in entry.get("versions") or []:
            parsed = update_registry._parse_version_entry(item)
            key = (name, parsed["version"])
            if base_versions.get(key) != parsed["api_version"]:
                changed.append((repo, parsed["version"], name))
    return changed


def revalidate_release(repo: str, tag: str, name: str) -> None:
    """Downloads and re-validates one changed release."""
    print(f"-> Re-validating {repo}@{tag}...")
    metadata = poll_releases.download_metadata(repo, tag)
    validate_addon.validate_schema(metadata)
    validate_addon.validate_content(metadata, tag=tag, name=name)
    verify_screenshots.verify_screenshots(repo, tag, metadata)


def main() -> int:
    """Main execution function for the script."""
    args = parse_arguments()
    try:
        registry = update_registry.load_yaml_file(args.registry_file)
        allowlist = update_registry.load_yaml_file(args.allowlist_file)
        print("-> Validating registry structure...")
        validate_structure(registry, allowlist)
        if args.base_file is not None:
            base = update_registry.load_yaml_file(args.base_file)
            releases = changed_releases(registry, base)
            for repo, tag, name in releases:
                revalidate_release(repo, tag, name)
            print(f"   ... {len(releases)} changed release(s) OK")
        print("\nSUCCESS: Registry is valid.")
        return 0
    except (OSError, ValueError, TypeError, KeyError, yaml.YAMLError) as e:
        print(f"\nERROR: Registry validation failed. {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())