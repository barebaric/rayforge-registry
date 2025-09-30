#!/usr/bin/env python3
import argparse
import yaml
import subprocess
import tempfile
import sys
from pathlib import Path

REGISTRY_FILE = "registry.yaml"


def get_package_metadata(repo_name, tag):
    """Clones the repo at a specific tag and reads its metadata file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_url = f"https://github.com/{repo_name}.git"
        print(f"Cloning {repo_url} at tag {tag}...")

        # Clone only the specific tag, with a depth of 1 for efficiency
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", tag, repo_url, "."],
            cwd=tmpdir,
            check=True,
            capture_output=True,
        )

        metadata_path = Path(tmpdir) / "rayforge-package.yaml"
        if not metadata_path.exists():
            raise FileNotFoundError(
                "rayforge-package.yaml not found in repository."
            )

        with open(metadata_path, "r") as f:
            return yaml.safe_load(f)


def update_registry(repo_name, tag, metadata):
    """Updates the registry.yaml file with the new version information."""
    with open(REGISTRY_FILE, "r") as f:
        registry_data = yaml.safe_load(f) or {"packages": {}}

    package_id = Path(repo_name).name

    # Get or create the entry for this package
    package_entry = registry_data["packages"].get(
        package_id,
        {
            "name": metadata["name"],
            "description": metadata.get("description", ""),
            "author": metadata.get("author", ""),
            "repository": f"https://github.com/{repo_name}",
            "versions": [],
        },
    )

    # Add the new version if it doesn't already exist
    if tag not in package_entry["versions"]:
        package_entry["versions"].append(tag)
        # A more robust implementation would use semantic version sorting
        package_entry["versions"].sort(reverse=True)

    # Update the latest stable version (simplistic: highest version is latest)
    package_entry["latest_stable"] = package_entry["versions"][0]

    registry_data["packages"][package_id] = package_entry

    with open(REGISTRY_FILE, "w") as f:
        yaml.safe_dump(registry_data, f, sort_keys=False)

    print(
        f"Successfully updated registry for {package_id} with version {tag}."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo", required=True, help="Repository name (owner/repo)"
    )
    parser.add_argument(
        "--tag", required=True, help="Git tag of the new release"
    )
    args = parser.parse_args()

    try:
        package_metadata = get_package_metadata(args.repo, args.tag)
        update_registry(args.repo, args.tag, package_metadata)
    except Exception as e:
        print(f"Error processing update: {e}")
        sys.exit(1)
