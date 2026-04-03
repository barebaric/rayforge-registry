#!/usr/bin/env python3
"""
Updates the main registry.yaml file with a new addon release.

This script reads a addon's validated metadata file, finds the
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
    A custom YAML dumper that adds a blank line before each addon entry
    in the 'addon' dictionary. This makes the registry file much easier
    for humans to read.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A flag to prevent a newline before the very first addon.
        self.first_addon_written = False

    def write_key(self):
        """
        Override to add a newline before each addon key, but not the
        first one.
        """
        # The PyYAML dumper's `self.indent` tracks the number of spaces.
        # We want to add a newline only for the addon keys, which are at
        # the correct indentation level (e.g., 2 spaces).
        if self.indent == self.best_indent:
            if self.first_addon_written:
                self.stream.write("\n")
            # After this key, any subsequent addon key should get a newline.
            self.first_addon_written = True

        super().write_key()  # type: ignore


def parse_arguments() -> argparse.Namespace:
    """
    Parses command-line arguments for the script.

    Returns:
        argparse.Namespace: The parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Update the registry with a new addon version."
    )
    parser.add_argument(
        "metadata_file",
        type=Path,
        help="Path to the validated rayforge-addon.yaml file.",
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


def _get_version_tag(entry):
    """Extract the version tag string from a version entry."""
    if isinstance(entry, dict):
        return entry.get("version", "")
    return str(entry)


def _parse_version_entry(entry):
    """
    Normalize a version entry to a dict.

    Supports both the legacy format (plain string) and the structured
    format (dict with 'version', 'api_version').
    """
    if isinstance(entry, dict):
        return {
            "version": entry.get("version", ""),
            "api_version": entry.get("api_version", 0),
        }
    return {"version": str(entry), "api_version": 0}


def update_addon_entry(
    registry_data: Dict, metadata: Dict, repo: str, tag: str
):
    """
    Updates or creates a addon entry within the registry data.

    This function modifies the registry_data dictionary in place.

    Args:
        registry_data: The full, current registry data.
        metadata: The addon's metadata from its YAML file.
        repo: The repository name (e.g., 'owner/name').
        tag: The new version tag (e.g., 'v1.2.3').
    """
    addon_name = metadata["name"]
    repository_url = f"https://github.com/{repo}"
    # Ensure 'addons' key exists at the top level.
    if "addons" not in registry_data:
        registry_data["addons"] = {}
    addons = registry_data["addons"]

    # Get or create the entry for this addon.
    addon_entry = addons.get(
        addon_name,
        {"repository": repository_url, "versions": []},
    )

    # Update static metadata from the addon file.
    depends = metadata.get("depends", [])
    if isinstance(depends, str):
        depends = [depends]

    api_version = metadata.get("api_version", 0)

    addon_entry.update(
        {
            "display_name": metadata.get("display_name", addon_name),
            "description": metadata.get("description", ""),
            "api_version": api_version,
            "depends": depends,
            "author": metadata.get("author", {}),
            "license": metadata.get("license"),
            "repository": repository_url,
        }
    )

    # Migrate legacy string-based version entries to structured dicts.
    addon_entry["versions"] = [
        _parse_version_entry(v) for v in addon_entry["versions"]
    ]

    # Build the new structured version entry.
    new_version_entry = {
        "version": tag,
        "api_version": api_version,
    }

    # Replace existing entry for this tag, or append.
    found = False
    for i, existing in enumerate(addon_entry["versions"]):
        if _get_version_tag(existing) == tag:
            addon_entry["versions"][i] = new_version_entry
            found = True
            break
    if not found:
        addon_entry["versions"].append(new_version_entry)

    # Sort versions using semantic versioning to ensure correctness.
    try:
        addon_entry["versions"].sort(
            key=lambda v: semver.VersionInfo.parse(
                _get_version_tag(v).lstrip("v")
            ),
            reverse=True,
        )
        # The highest valid version is the latest stable release.
        addon_entry["latest_stable"] = _get_version_tag(
            addon_entry["versions"][0]
        )
    except ValueError as e:
        print(
            f"WARNING: Could not sort versions for '{addon_name}' due to "
            f"invalid semantic version. {e}",
            file=sys.stderr,
        )

    # Sort the keys within this specific addon entry for consistency
    sorted_addon_entry = {
        "display_name": addon_entry.get("display_name", addon_name),
        "description": addon_entry.get("description", ""),
        "api_version": addon_entry.get("api_version"),
        "depends": addon_entry.get("depends", []),
        "author": addon_entry.get("author", {}),
        "license": addon_entry.get("license"),
        "repository": addon_entry["repository"],
        "latest_stable": addon_entry.get("latest_stable", ""),
        "versions": addon_entry["versions"],
    }

    addons[addon_name] = sorted_addon_entry

    registry_data["addons"] = dict(sorted(addons.items()))


def main() -> int:
    """Main execution function for the script."""
    args = parse_arguments()

    try:
        # Load both the addon metadata and the current registry.
        metadata = load_yaml_file(args.metadata_file)
        registry = load_yaml_file(REGISTRY_FILE)

        # Perform the update logic.
        update_addon_entry(registry, metadata, args.repo, args.tag)

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
