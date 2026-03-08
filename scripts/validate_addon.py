#!/usr/bin/env python3
"""
Validates a Rayforge addon's metadata for the registry server.

This script checks a given 'rayforge-addon.yaml' metadata file for
schema correctness and content consistency.
"""

import argparse
import re
import sys
from pathlib import Path

import semver
import yaml

METADATA_FILENAME = "rayforge-addon.yaml"

SCHEMA = {
    "name": {"type": str, "required": True},
    "description": {"type": str, "required": True},
    "api_version": {"type": int, "required": True},
    "depends": {"type": list, "required": True},
    "author": {"type": dict, "required": True},
    "provides": {"type": dict, "required": True},
    "license": {"type": dict, "required": False},
}

AUTHOR_SCHEMA = {
    "name": {"type": str, "required": True},
    "email": {"type": str, "required": True},
}


def _check_non_empty_str(value, key_name):
    """Raises ValueError if a string is None, empty, or just whitespace."""
    if not value or not value.strip():
        raise ValueError(f"Key '{key_name}' must not be empty.")


def _check_depends(depends_data):
    """Validates the 'depends' section."""
    if not depends_data or not isinstance(depends_data, list):
        raise ValueError("'depends' must be a non-empty list.")

    for dep in depends_data:
        if not isinstance(dep, str):
            raise ValueError(f"Dependency must be a string: {dep}")

        parts = dep.split(",")
        if not parts or not parts[0]:
            raise ValueError(f"Invalid dependency format: {dep}")

        pkg_part = parts[0].strip()
        if not pkg_part:
            raise ValueError(f"Invalid dependency format: {dep}")

        for constraint in parts[1:]:
            constraint = constraint.strip()
            if not constraint:
                continue

            op_match = re.match(r"^([~^><=!]+)(.+)$", constraint)
            if not op_match:
                raise ValueError(
                    f"Invalid version constraint '{constraint}' in: {dep}"
                )

            version_str = op_match.group(2).lstrip("v")
            operator = op_match.group(1)

            if operator == "~":
                version_parts = version_str.split(".")
                if len(version_parts) == 2:
                    version_str = f"{version_str}.0"
                elif len(version_parts) == 1:
                    version_str = f"{version_str}.0.0"

            try:
                semver.VersionInfo.parse(version_str)
            except ValueError:
                raise ValueError(
                    f"Invalid semantic version in constraint "
                    f"'{constraint}': {dep}"
                )


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


def _check_api_version(api_version):
    """Validates that api_version is a positive integer."""
    if not isinstance(api_version, int):
        raise ValueError(
            f"api_version must be an integer, got: "
            f"{type(api_version).__name__}"
        )
    if api_version < 1:
        raise ValueError(
            f"api_version must be a positive integer, got: {api_version}"
        )
    print(f"   ... API version {api_version} OK")


def _check_tag(tag):
    """Validates that a tag is a valid semantic version."""
    if not tag:
        print(
            "   ... WARNING: No tag provided. Git tags are required for "
            "installable addons."
        )
        return
    try:
        semver.VersionInfo.parse(tag.lstrip("v"))
        print(f"   ... Version tag '{tag}' OK")
    except ValueError:
        raise ValueError(
            f"Version tag '{tag}' is not a valid semantic version "
            "(e.g., v1.2.3)."
        )


def _check_addon_name(metadata_name, expected_name):
    """Validates addon name in metadata against the expected one."""
    if not expected_name:
        return
    if metadata_name != expected_name:
        raise ValueError(
            f"Addon name mismatch. Expected '{expected_name}', but "
            f"metadata has '{metadata_name}'."
        )
    print(f"   ... Addon name '{expected_name}' OK")


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

    email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if not re.match(email_regex, email):
        raise ValueError(f"Author email '{email}' has an invalid format.")


def _is_valid_module_path(path: str) -> bool:
    """Check if a string is a valid Python module path."""
    if not path or path.startswith(".") or path.endswith("."):
        return False
    parts = path.split(".")
    return all(part.isidentifier() for part in parts)


def _check_entry_point(entry_point, field_name):
    """Validates a Python module entry point format."""
    if entry_point is None:
        return
    if not _is_valid_module_path(entry_point):
        raise ValueError(
            f"'{field_name}' entry point '{entry_point}' is not a valid "
            "module path. Use dotted notation (e.g., 'my_addon.backend')."
        )
    print(f"   ... {field_name} entry point '{entry_point}' OK")


def _check_provides(provides_data):
    """Validates the structure of the 'provides' section."""
    if not provides_data or not (
        "backend" in provides_data
        or "frontend" in provides_data
        or "assets" in provides_data
    ):
        raise ValueError(
            "The 'provides' section must contain 'backend', "
            "'frontend', and/or 'assets'."
        )

    if "backend" in provides_data:
        backend = provides_data["backend"]
        if not isinstance(backend, str):
            raise TypeError("'provides.backend' must be a string.")
        _check_entry_point(backend, "backend")

    if "frontend" in provides_data:
        frontend = provides_data["frontend"]
        if not isinstance(frontend, str):
            raise TypeError("'provides.frontend' must be a string.")
        _check_entry_point(frontend, "frontend")

    if "assets" in provides_data:
        assets = provides_data["assets"]
        if not isinstance(assets, list):
            raise TypeError("'provides.assets' must be a list.")
        for i, asset_info in enumerate(assets):
            if not isinstance(asset_info, dict):
                raise TypeError(
                    f"'provides.assets[{i}]' must be a dictionary."
                )
            if "path" not in asset_info:
                raise ValueError(
                    f"'provides.assets[{i}]' must have a 'path' key."
                )
        print(f"   ... {len(assets)} asset(s) declared")


def _check_license(license_data):
    """Validates the optional 'license' section."""
    if license_data is None:
        return
    if not isinstance(license_data, dict):
        raise TypeError("'license' must be a dictionary.")
    name = license_data.get("name")
    if name is not None:
        if not isinstance(name, str):
            raise TypeError("'license.name' must be a string.")
        if not name.strip():
            raise ValueError("'license.name' must not be empty.")
        print(f"   ... License '{name}' OK")


def validate_content(data, tag=None, name=None):
    """Performs sanity checks on the metadata content."""
    print("-> Running content validation...")
    _check_tag(tag)
    _check_addon_name(data.get("name"), name)
    _check_api_version(data.get("api_version"))

    _check_non_empty_str(data.get("name"), "name")
    _check_non_empty_str(data.get("description"), "description")

    _check_depends(data.get("depends", []))
    _check_author_content(data.get("author", {}))
    _check_provides(data.get("provides", {}))
    _check_license(data.get("license"))
    print("   ... Content OK")


def main():
    """Main execution function. Parses arguments and runs validations."""
    parser = argparse.ArgumentParser(
        description="Validate a Rayforge addon's metadata."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to addon root directory (defaults to current dir).",
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="The Git tag to validate (used by CI).",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="The expected addon name (used by CI).",
    )
    args = parser.parse_args()

    root_path = Path(args.path).resolve()
    metadata_file = root_path / METADATA_FILENAME
    print(f"Validating addon at: {root_path}")

    try:
        if not metadata_file.is_file():
            raise FileNotFoundError(
                f"Metadata file not found: {metadata_file}"
            )

        with open(metadata_file, "r") as f:
            metadata = yaml.safe_load(f)
        if not isinstance(metadata, dict):
            raise TypeError(
                f"'{METADATA_FILENAME}' must be a YAML dictionary."
            )

        validate_schema(metadata)
        validate_content(metadata, tag=args.tag, name=args.name)

        print("\nSUCCESS: Your addon metadata is valid!")
        return 0

    except (ValueError, TypeError, FileNotFoundError, NameError) as e:
        print(f"\nERROR: Validation failed. {e}", file=sys.stderr)
        return 1
    except yaml.YAMLError as e:
        print(
            f"\nERROR: Could not parse '{METADATA_FILENAME}'. {e}",
            file=sys.stderr,
        )
        return 1
    except Exception as e:
        print(f"\nERROR: An unexpected error occurred. {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
