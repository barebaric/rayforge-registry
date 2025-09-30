#!/usr/bin/env python3
"""
Validates a Rayforge package's metadata for the registry server.

This script checks a given 'rayforge-package.yaml' metadata file for
schema correctness and content consistency.
"""

import argparse
import re
import sys
from pathlib import Path

import semver
import yaml

# Schema defines required keys and their expected types.
SCHEMA = {
    "name": {"type": str, "required": True},
    "description": {"type": str, "required": True},
    "author": {"type": dict, "required": True},
    "provides": {"type": dict, "required": True},
}

AUTHOR_SCHEMA = {
    "name": {"type": str, "required": True},
    "email": {"type": str, "required": True},
}


def _check_non_empty_str(value, key_name):
    """Raises ValueError if a string is None, empty, or just whitespace."""
    if not value or not value.strip():
        raise ValueError(f"Key '{key_name}' must not be empty.")


def _validate_dict_schema(data, schema, parent_key=""):
    """Validates a dictionary against a defined schema."""
    for key, rules in schema.items():
        full_key = f"{parent_key}.{key}" if parent_key else key
        if rules.get("required") and key not in data:
            raise ValueError(f"Missing required key: '{full_key}'")

        if key in data:
            expected_type = rules["type"]
            actual_value = data[key]
            if not isinstance(actual_value, expected_type):
                raise TypeError(
                    f"Key '{full_key}' has wrong type. "
                    f"Expected {expected_type.__name__}, but "
                    f"got {type(actual_value).__name__}."
                )


def validate_schema(data):
    """Checks for required keys and correct types in the metadata."""
    print("-> Running schema validation...")
    _validate_dict_schema(data, SCHEMA)
    _validate_dict_schema(data.get("author", {}), AUTHOR_SCHEMA, "author")
    print("   ... Schema OK")


def _check_tag(tag):
    """Validates that a tag is a valid semantic version."""
    if not tag:
        return
    try:
        semver.VersionInfo.parse(tag.lstrip("v"))
        print(f"   ... Version tag '{tag}' OK")
    except ValueError:
        raise ValueError(
            f"Version tag '{tag}' is not a valid semantic version "
            "(e.g., v1.2.3)."
        )


def _check_author_content(author_data):
    """Checks for placeholders and valid content in the author field."""
    name = author_data.get("name", "")
    email = author_data.get("email", "")

    _check_non_empty_str(name, "author.name")
    _check_non_empty_str(email, "author.email")

    if "your-github-username" in name:
        raise ValueError(
            "Placeholder 'author.name' detected. Please update it."
        )

    # Basic email regex to catch common mistakes.
    email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if not re.match(email_regex, email):
        raise ValueError(f"Author email '{email}' has an invalid format.")


def _check_provides(provides_data):
    """Validates the structure of the 'provides' section."""
    if not provides_data or not (
        "code" in provides_data or "assets" in provides_data
    ):
        raise ValueError(
            "The 'provides' section must contain 'code' and/or 'assets'."
        )

    if "assets" in provides_data:
        if not isinstance(provides_data["assets"], list):
            raise TypeError("'provides.assets' must be a list.")

    if "code" in provides_data:
        if not isinstance(provides_data["code"], str):
            raise TypeError("'provides.code' must be a string.")


def validate_content(data, tag=None):
    """Performs sanity checks on the metadata content."""
    print("-> Running content validation...")
    _check_tag(tag)
    _check_non_empty_str(data.get("name"), "name")
    _check_non_empty_str(data.get("description"), "description")
    _check_author_content(data.get("author", {}))
    _check_provides(data.get("provides", {}))
    print("   ... Content OK")


def main():
    """Main execution function. Parses arguments and runs validations."""
    parser = argparse.ArgumentParser(
        description="Validate a Rayforge package's metadata."
    )
    parser.add_argument(
        "metadata_file",
        type=Path,
        help="Path to the rayforge-package.yaml file to validate.",
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="The Git tag to validate (used by CI).",
    )
    args = parser.parse_args()

    print(f"Validating metadata file: {args.metadata_file}")

    try:
        if not args.metadata_file.is_file():
            raise FileNotFoundError(f"File not found: {args.metadata_file}")

        with open(args.metadata_file, "r") as f:
            metadata = yaml.safe_load(f)
        if not isinstance(metadata, dict):
            raise TypeError(
                f"'{args.metadata_file.name}' must be a YAML dictionary."
            )

        validate_schema(metadata)
        validate_content(metadata, tag=args.tag)

        print("\nSUCCESS: Your package metadata is valid!")
        return 0

    except (ValueError, TypeError, FileNotFoundError, NameError) as e:
        print(f"\nERROR: Validation failed. {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\nERROR: An unexpected error occurred. {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
