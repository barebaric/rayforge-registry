#!/usr/bin/env python3
"""
Updates the main registry.yaml file with a new package release.

This script reads a package's validated metadata file, finds the
corresponding entry in the main registry, and adds or updates the
version information with improved, human-readable formatting.
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict

import semver
import yaml

REGISTRY_FILE = Path("registry.yaml")


class NiceDumper(yaml.SafeDumper):
    """
    A custom YAML dumper that adds a blank line before each package entry
    in the 'packages' dictionary. This makes the registry file much easier
    for humans to read.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A flag to prevent a newline before the very first package.
        self.first_package_written = False

    def write_key(self):
        """
        Override to add a newline before each package key, but not the
        first one.
        """
        # The PyYAML dumper's `self.indent` tracks the number of spaces.
        # We want to add a newline only for the package keys, which are at
        # the correct indentation level (e.g., 2 spaces).
        if self.indent == self.best_indent:
            if self.first_package_written:
                self.stream.write("\n")
            # After this key, any subsequent package key should get a newline.
            self.first_package_written = True

        super().write_key()  # type: ignore


def parse_arguments() -> argparse.Namespace:
    """
    Parses command-line arguments for the script.

    Returns:
        argparse.Namespace: The parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Update the registry with a new package version."
    )
    parser.add_argument(
        "metadata_file",
        type=Path,
        help="Path to the validated rayforge-package.yaml file.",
    )
    parser.add_argument(
        "--repo", required=True, help="Repository name (owner/repo)"
    )
    parser.add_argument(
        "--tag", required=True, help="Git tag of the new release"
    )
    return parser.parse_args()


def load_yaml_file(file_path: Path) -> Dict[str, Any]:
    """
    Loads and parses a YAML file.

    Args:
        file_path (Path): The path to the YAML file.

    Returns:
        A dictionary containing the parsed YAML data.

    Raises:
        FileNotFoundError: If the file does not exist.
        yaml.YAMLError: If the file is not valid YAML.
    """
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        return data if data is not None else {}


def save_yaml_file(data: Dict[str, Any], file_path: Path):
    """
    Saves a dictionary to a YAML file with nice formatting.

    Args:
        data (dict): The dictionary to save.
        file_path (Path): The path to the output YAML file.
    """
    indent_level = 2
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.dump(
            data,
            f,
            Dumper=NiceDumper,
            sort_keys=False,
            default_flow_style=False,
            indent=indent_level,
        )


def update_package_entry(
    registry_data: Dict, metadata: Dict, repo: str, tag: str
):
    """
    Updates or creates a package entry within the registry data.

    This function modifies the registry_data dictionary in place.

    Args:
        registry_data: The full, current registry data.
        metadata: The package's metadata from its YAML file.
        repo: The repository name (e.g., 'owner/name').
        tag: The new version tag (e.g., 'v1.2.3').
    """
    package_id = Path(repo).name
    # Ensure 'packages' key exists at the top level.
    if "packages" not in registry_data:
        registry_data["packages"] = {}
    packages = registry_data["packages"]

    # Get or create the entry for this package.
    package_entry = packages.get(
        package_id,
        {"repository": f"https://github.com/{repo}", "versions": []},
    )

    # Update static metadata from the package file.
    package_entry.update(
        {
            "name": metadata["name"],
            "description": metadata.get("description", ""),
            "author": metadata.get("author", {}),
        }
    )

    # Add the new version if it doesn't already exist.
    if tag not in package_entry["versions"]:
        package_entry["versions"].append(tag)

    # Sort versions using semantic versioning to ensure correctness.
    try:
        package_entry["versions"].sort(
            key=lambda v: semver.VersionInfo.parse(v.lstrip("v")),
            reverse=True,
        )
        # The highest valid version is the latest stable release.
        package_entry["latest_stable"] = package_entry["versions"][0]
    except ValueError as e:
        print(
            f"WARNING: Could not sort versions for '{package_id}' due to "
            f"invalid semantic version. {e}",
            file=sys.stderr,
        )

    # Sort the keys within this specific package entry for consistency
    sorted_package_entry = {
        "name": package_entry["name"],
        "description": package_entry.get("description", ""),
        "author": package_entry.get("author", {}),
        "repository": package_entry["repository"],
        "latest_stable": package_entry.get("latest_stable", ""),
        "versions": package_entry["versions"],
    }

    packages[package_id] = sorted_package_entry

    registry_data["packages"] = dict(sorted(packages.items()))


def main() -> int:
    """Main execution function for the script."""
    args = parse_arguments()

    try:
        # Load both the package metadata and the current registry.
        metadata = load_yaml_file(args.metadata_file)
        registry = load_yaml_file(REGISTRY_FILE)

        # Perform the update logic.
        update_package_entry(registry, metadata, args.repo, args.tag)

        # Save the modified registry back to the file.
        save_yaml_file(registry, REGISTRY_FILE)

        print(
            f"Successfully updated registry for {Path(args.repo).name}"
            f"@{args.tag}."
        )
        return 0

    except (FileNotFoundError, yaml.YAMLError, ValueError) as e:
        print(f"ERROR: Could not update registry. {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: An unexpected error occurred. {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
