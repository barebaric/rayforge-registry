#!/usr/bin/env python3
import sys
from pathlib import Path

import yaml

ALLOWLIST_FILE = Path("allowed-repositories.yaml")

# A safe default mode if 'mode' is not specified for an allowed repository.
DEFAULT_MODE = "pr"


def get_commit_mode(repo_to_check, data):
    """
    Returns the commit mode configured for the given repository.

    Raises ValueError if the repository is not on the allowlist.
    """
    for item in data.get("repositories", []):
        if item.get("repo") == repo_to_check:
            mode = item.get("mode", DEFAULT_MODE)
            if mode not in ["direct", "pr"]:
                print(
                    f"Warning: Invalid mode '{mode}' for "
                    f"'{repo_to_check}'. "
                    f"Falling back to safe default '{DEFAULT_MODE}'.",
                    file=sys.stderr,
                )
                mode = DEFAULT_MODE

            # Success: Print the mode to stdout for the workflow
            # to capture.
            return mode

    # If the lookup completes, the repository was not found. This is an
    # authorization failure.
    raise ValueError(
        f"Repository '{repo_to_check}' is not on the allowlist."
    )


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: python authorize_and_get_mode.py <owner/repo>",
            file=sys.stderr,
        )
        sys.exit(1)

    repo_to_check = sys.argv[1]

    try:
        with open(ALLOWLIST_FILE, "r") as f:
            data = yaml.safe_load(f)

        print(get_commit_mode(repo_to_check, data))
        sys.exit(0)

    except ValueError as e:
        print(f"❌ Authorization FAILED: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(
            f"❌ Authorization FAILED: Allowlist '{ALLOWLIST_FILE}' not found.",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(
            f"❌ Authorization FAILED: An unexpected error occurred. {e}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
