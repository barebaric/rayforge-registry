#!/usr/bin/env python3
"""
Validates a Rayforge package for correctness.

This script checks the 'rayforge-package.yaml' metadata file for schema
correctness, content consistency, and the existence of declared assets.

It can be run locally (e.g., as a pre-commit hook) or in a CI/CD
pipeline.
"""

import argparse
import sys
import yaml
import semver
from pathlib import Path

# The expected schema for the 'rayforge-package.yaml' metadata file.
SCHEMA = {
    "name": str,
    "description": str,
    "author": str,
    "provides": dict,
}


def validate_schema(data):
    """
    Checks for required keys and correct types in the metadata.

    Args:
        data (dict): The parsed YAML data from the metadata file.

    Raises:
        ValueError: If a required key is missing.
        TypeError: If a key has an incorrect value type.
    """
    print("-> Running schema validation...")
    for key, expected_type in SCHEMA.items():
        if key not in data:
            raise ValueError(f"Missing required key in metadata: '{key}'")
        if not isinstance(data[key], expected_type):
            raise TypeError(
                f"Key '{key}' has wrong type. Expected {expected_type}, "
                f"got {type(data[key])}."
            )
    print("   ... Schema OK")


def validate_content(data, root_path, tag=None, name=None):
    """
    Performs sanity checks on the metadata content.

    Args:
        data (dict): The parsed YAML data from the metadata file.
        root_path (Path): The root directory of the package to validate.
        tag (str, optional): The Git tag to validate.
        name (str, optional): The expected package name to validate.

    Raises:
        ValueError: If any content is inconsistent, invalid, or uses
                    placeholder values.
        FileNotFoundError: If a declared asset path does not exist.
    """
    print("-> Running content validation...")

    # If a tag is provided (e.g., in remote CI), validate it.
    if tag:
        try:
            semver.VersionInfo.parse(tag.lstrip("v"))
        except ValueError:
            raise ValueError(
                f"Version tag '{tag}' is not a valid semantic version "
                "(e.g., v1.2.3)."
            )
        print(f"   ... Version tag '{tag}' OK")

    # If a package name is provided (e.g., in remote CI), validate it.
    if name:
        if data.get("name") != name:
            raise ValueError(
                f"Package name mismatch. Expected '{name}', but "
                f"metadata has '{data.get('name')}'."
            )
        print(f"   ... Package name '{name}' OK")

    # Check for placeholder values that should have been changed.
    if "your-github-username" in data.get("author", ""):
        raise ValueError(
            "Placeholder 'author' value detected. Please update it."
        )

    # Check that declared asset paths exist and are secure.
    if "assets" in data.get("provides", {}):
        for asset_info in data["provides"]["assets"]:
            path_str = asset_info.get("path")
            if not path_str:
                raise ValueError("Asset entry is missing the 'path' key.")

            asset_path = root_path / path_str
            if not asset_path.exists():
                raise FileNotFoundError(
                    f"Asset path '{path_str}' does not exist."
                )
            if ".." in Path(path_str).parts:
                raise ValueError(
                    f"Invalid asset path: '{path_str}'. "
                    "Paths must not use '..'."
                )
    print("   ... Content OK")


def main():
    """
    Main execution function. Parses arguments and runs validations.
    """
    parser = argparse.ArgumentParser(
        description="Validate a Rayforge package."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to the package root directory (defaults to current dir).",
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="The Git tag to validate (used by CI, optional locally).",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="The expected package name (used by CI, optional locally).",
    )
    args = parser.parse_args()

    root_path = Path(args.path).resolve()
    metadata_file = root_path / "rayforge-package.yaml"
    print(f"Validating package at: {root_path}")

    if not metadata_file.is_file():
        print(
            f"\nERROR: Metadata file not found at '{metadata_file}'",
            file=sys.stderr,
        )
        return 1

    try:
        with open(metadata_file, "r") as f:
            metadata = yaml.safe_load(f)

        validate_schema(metadata)
        validate_content(metadata, root_path, tag=args.tag, name=args.name)

        print("\nSUCCESS: Your package metadata looks great!")
        return 0

    except (ValueError, TypeError, FileNotFoundError) as e:
        print(f"\nERROR: Validation failed. {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\nERROR: An unexpected error occurred. {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
