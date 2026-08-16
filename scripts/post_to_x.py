#!/usr/bin/env python3
"""Publish a single post to the official Know the Gulf X account.

Text posts use OAuth 1.0a user-context credentials. For images, the publisher
prefers X API v2 media upload when an OAuth 2.0 user access token is available,
and otherwise uses X's still-supported legacy media-upload endpoint with the
same OAuth 1.0a user context. Secrets are never printed.
"""

from __future__ import annotations

import argparse
import base64
import os
import sys
from pathlib import Path

import requests
from requests_oauthlib import OAuth1

API_URL = "https://api.x.com/2/tweets"
MEDIA_V2_URL = "https://api.x.com/2/media/upload"
MEDIA_LEGACY_URL = "https://upload.x.com/1.1/media/upload.json"
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
    parser.add_argument("--media", help="Optional PNG/JPEG image path")
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
        raise ValueError(f"Post is {len(text)} characters; limit is {MAX_POST_LENGTH}")
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


def maybe_generate_condition_card(text: str) -> Path | None:
    """Generate a card only for current-condition/flag-change posts."""
    lowered = text.lower()
    if "gulf coast flag check" not in lowered and "beach flag update" not in lowered and "beach flag updates" not in lowered:
        return None
    try:
        from generate_x_condition_card import draw_card
        out = Path(__file__).resolve().parents[1] / "tmp" / "x-condition-card.png"
        title = "Beach Flag Update" if "flag update" in lowered else "Northwest Florida Gulf Check"
        draw_card(out, title)
        return out
    except Exception as exc:
        print(f"WARNING: condition card generation failed; continuing text-only: {exc}", file=sys.stderr)
        return None


def upload_media_v2(path: Path, token: str) -> str:
    raw = path.read_bytes()
    if len(raw) > 5 * 1024 * 1024:
        raise RuntimeError("Image exceeds X's 5 MB image upload limit")
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    response = requests.post(
        MEDIA_V2_URL,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "media": base64.b64encode(raw).decode("ascii"),
            "media_category": "tweet_image",
            "media_type": mime,
            "shared": False,
        },
        timeout=45,
    )
    if response.status_code not in {200, 201}:
        raise RuntimeError(f"X v2 media upload returned HTTP {response.status_code}: {response.text[:1000]}")
    payload = response.json()
    media_id = payload.get("data", {}).get("id")
    if not media_id:
        raise RuntimeError("X v2 media upload response did not include a media id")
    return str(media_id)


def upload_media_legacy(path: Path) -> str:
    if path.stat().st_size > 5 * 1024 * 1024:
        raise RuntimeError("Image exceeds X's 5 MB image upload limit")
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    with path.open("rb") as fh:
        response = requests.post(
            MEDIA_LEGACY_URL,
            auth=get_auth(),
            files={"media": (path.name, fh, mime)},
            data={"media_category": "tweet_image"},
            timeout=45,
        )
    if response.status_code not in {200, 201, 202}:
        raise RuntimeError(f"X legacy media upload returned HTTP {response.status_code}: {response.text[:1000]}")
    payload = response.json()
    media_id = payload.get("media_id_string") or payload.get("media_id") or payload.get("data", {}).get("id")
    if not media_id:
        raise RuntimeError("X legacy media upload response did not include a media id")
    return str(media_id)


def upload_media(path: Path) -> str:
    oauth2 = os.getenv("X_OAUTH2_ACCESS_TOKEN", "").strip()
    if oauth2:
        return upload_media_v2(path, oauth2)
    return upload_media_legacy(path)


def publish(text: str, media_path: str | Path | None = None) -> tuple[str, str]:
    text = validate_text(text)
    resolved_media: Path | None = Path(media_path) if media_path else None
    if resolved_media is None:
        env_media = os.getenv("X_MEDIA_PATH", "").strip()
        resolved_media = Path(env_media) if env_media else maybe_generate_condition_card(text)

    body: dict = {"text": text}
    if resolved_media and resolved_media.exists():
        try:
            media_id = upload_media(resolved_media)
            body["media"] = {"media_ids": [media_id]}
            print(f"Attached condition card: {resolved_media.name}")
        except Exception as exc:
            # Safety information is more important than the graphic. A media API
            # disruption must not suppress a time-sensitive flag-change post.
            print(f"WARNING: media upload failed; publishing text-only: {exc}", file=sys.stderr)

    response = requests.post(
        API_URL,
        auth=get_auth(),
        json=body,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    if response.status_code != 201:
        raise RuntimeError(f"X API returned HTTP {response.status_code}: {response.text[:2000]}")

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
            if args.media:
                print(f"Media requested: {args.media}")
            print(text)
            return 0
        post_id, _ = publish(text, args.media)
        print("Post published successfully.")
        print(f"Post ID: {post_id}")
        print(f"URL: https://x.com/{ACCOUNT_HANDLE}/status/{post_id}")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
