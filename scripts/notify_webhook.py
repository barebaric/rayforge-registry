#!/usr/bin/env python3
"""
Sends a pull request notification to a Slack or Discord webhook.

The webhook URL is read from the NOTIFY_WEBHOOK_URL environment
variable. When it is not set, the notification is skipped so the
calling workflow keeps working before the secret is configured.
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

REQUEST_TIMEOUT = 30
USER_AGENT = "rayforge-registry-notifier"


def parse_arguments() -> argparse.Namespace:
    """Parses command-line arguments for the script."""
    parser = argparse.ArgumentParser(
        description="Notify a Slack or Discord webhook about a new PR."
    )
    parser.add_argument("--title", required=True, help="PR title.")
    parser.add_argument("--url", required=True, help="PR URL.")
    parser.add_argument("--status", required=True, help="Outcome line.")
    parser.add_argument(
        "--details", default="", help="Optional extra lines."
    )
    return parser.parse_args()


def build_message(args: argparse.Namespace) -> str:
    """Formats the notification text."""
    lines = [
        f"New registry PR: {args.title}",
        args.url,
        f"Status: {args.status}",
    ]
    if args.details:
        lines.append(args.details)
    return "\n".join(lines)


def build_payload(webhook_url: str, message: str) -> dict:
    """Builds a webhook payload for Slack or Discord."""
    host = urllib.parse.urlparse(webhook_url).netloc
    if "discord" in host:
        return {"content": message}
    return {"text": message}


def send_notification(webhook_url: str, message: str) -> None:
    """Posts the message to the webhook. Raises OSError on failure."""
    payload = build_payload(webhook_url, message)
    request = urllib.request.Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    with urllib.request.urlopen(
        request, timeout=REQUEST_TIMEOUT
    ) as response:
        response.read()


def main() -> int:
    """Main execution function for the script."""
    args = parse_arguments()
    webhook_url = os.environ.get("NOTIFY_WEBHOOK_URL", "").strip()
    if not webhook_url:
        print("NOTIFY_WEBHOOK_URL is not set; skipping notification.")
        return 0
    try:
        send_notification(webhook_url, build_message(args))
        print("Notification sent.")
    except (OSError, ValueError) as e:
        print(
            f"WARNING: Could not send notification. {e}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())