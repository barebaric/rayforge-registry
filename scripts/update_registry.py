#!/usr/bin/env python3
"""
Updates the main registry.yaml file with a new package release.

This script reads a package's validated metadata file, finds the
corresponding entry in the main registry, and adds or updates the
version information.
"""

import argparse
import sys
from pathlib import Path

import semver
import yaml

REGISTRY_FILE = Path("registry.yaml")


def parse_arguments():
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


def load_yaml_file(file_path):
    """
    Loads and parses a YAML file.

    Args:
        file_path (Path): The path to the YAML file.

    Returns:
        dict: The parsed YAML data as a dictionary.

    Raises:
        FileNotFoundError: If the file does not exist.
        yaml.YAMLError: If the file is not valid YAML.
    """
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")
    with open(file_path, "r") as f:
        return yaml.safe_load(f)


def save_yaml_file(data, file_path):
    """
    Saves a dictionary to a YAML file.

    Args:
        data (dict): The dictionary to save.
        file_path (Path): The path to the output YAML file.
    """
    with open(file_path, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False)


def update_package_entry(registry_data, metadata, repo, tag):
    """
    Updates or creates a package entry within the registry data.

    This function modifies the registry_data dictionary in place.

    Args:
        registry_data (dict): The full, current registry data.
        metadata (dict): The package's metadata from its YAML file.
        repo (str): The repository name (e.g., 'owner/name').
        tag (str): The new version tag (e.g., 'v1.2.3').
    """
    package_id = Path(repo).name
    packages = registry_data.setdefault("packages", {})

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
    package_entry["versions"].sort(
        key=lambda v: semver.VersionInfo.parse(v.lstrip("v")),
        reverse=True,
    )

    # The highest valid version is the latest stable release.
    package_entry["latest_stable"] = package_entry["versions"][0]

    packages[package_id] = package_entry


def main():
    """Main execution function for the script."""
    args = parse_arguments()

    try:
        # Load both the package metadata and the current registry.
        metadata = load_yaml_file(args.metadata_file)
        registry = load_yaml_file(REGISTRY_FILE) or {}

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
