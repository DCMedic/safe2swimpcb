#!/usr/bin/env python3
"""Publish a single post to the official Know the Gulf X account.

Uses OAuth 1.0a user-context credentials supplied exclusively through
environment variables. Secrets are never printed.
"""

from __future__ import annotations

import argparse
import os
import sys

import requests
from requests_oauthlib import OAuth1

API_URL = "https://api.x.com/2/tweets"
ACCOUNT_HANDLE = "knowthegulf"
MAX_POST_LENGTH = 280
REQUIRED_ENV = (
    "X_API_KEY",
    "X_API_KEY_SECRET",
    "X_ACCESS_TOKEN",
    "X_ACCESS_TOKEN_SECRET",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish one Know the Gulf post to X")
    parser.add_argument("--text", required=True, help="Post text")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and display the text without contacting X",
    )
    return parser.parse_args()


def validate_text(text: str) -> str:
    text = text.strip()
    if not text:
        raise ValueError("Post text cannot be empty")
    if len(text) > MAX_POST_LENGTH:
        raise ValueError(
            f"Post is {len(text)} characters; keep manual test posts at or below "
            f"{MAX_POST_LENGTH} characters"
        )
    return text


def get_auth() -> OAuth1:
    missing = [name for name in REQUIRED_ENV if not os.getenv(name)]
    if missing:
        raise RuntimeError("Missing required GitHub Actions secrets: " + ", ".join(missing))

    return OAuth1(
        os.environ["X_API_KEY"],
        os.environ["X_API_KEY_SECRET"],
        os.environ["X_ACCESS_TOKEN"],
        os.environ["X_ACCESS_TOKEN_SECRET"],
    )


def publish(text: str) -> tuple[str, str]:
    response = requests.post(
        API_URL,
        auth=get_auth(),
        json={"text": text},
        headers={"Content-Type": "application/json"},
        timeout=30,
    )

    if response.status_code != 201:
        # X error bodies are useful for diagnosis and do not contain our OAuth secrets.
        body = response.text[:2000]
        raise RuntimeError(f"X API returned HTTP {response.status_code}: {body}")

    payload = response.json()
    post_id = str(payload["data"]["id"])
    returned_text = str(payload["data"].get("text", text))
    return post_id, returned_text


def main() -> int:
    args = parse_args()
    try:
        text = validate_text(args.text)
        if args.dry_run:
            print(f"DRY RUN: validated {len(text)} characters")
            print(text)
            return 0

        post_id, _ = publish(text)
        print("Post published successfully.")
        print(f"Post ID: {post_id}")
        print(f"URL: https://x.com/{ACCOUNT_HANDLE}/status/{post_id}")
        return 0
    except Exception as exc:  # concise failure for Actions logs
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
