#!/usr/bin/env python3
import sys
import yaml

# A safe default mode if 'mode' is not specified for an allowed repository.
DEFAULT_MODE = "pr"


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: python authorize_and_get_mode.py <owner/repo>",
            file=sys.stderr,
        )
        sys.exit(1)

    repo_to_check = sys.argv[1]
    allowlist_file = "allowed-repositories.yaml"

    try:
        with open(allowlist_file, "r") as f:
            data = yaml.safe_load(f)

        for item in data.get("repositories", []):
            if item.get("repo") == repo_to_check:
                mode = item.get("mode", DEFAULT_MODE)
                if mode not in ["direct", "pr"]:
                    print(
                        f"Warning: Invalid mode '{mode}'"
                        f"for '{repo_to_check}'. "
                        f"Falling back to safe default '{DEFAULT_MODE}'.",
                        file=sys.stderr,
                    )
                    mode = DEFAULT_MODE

                # Success: Print the mode to stdout for the workflow
                # to capture.
                print(mode)
                sys.exit(0)

        # If the loop completes, the repository was not found. This is an
        # authorization failure.
        print(
            f"❌ Authorization FAILED: Repository '{repo_to_check}' "
            "is not on the allowlist.",
            file=sys.stderr,
        )
        sys.exit(1)

    except FileNotFoundError:
        print(
            f"❌ Authorization FAILED: Allowlist '{allowlist_file}' not found.",
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
