#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

from update_southwest_locations import DATA, LOCATIONS, collect


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in LOCATIONS:
        choices = ", ".join(sorted(LOCATIONS))
        raise SystemExit(f"usage: {Path(sys.argv[0]).name} <slug>; choices: {choices}")

    slug = sys.argv[1]
    payload = collect(slug, LOCATIONS[slug])
    out = DATA / slug
    out.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2) + "\n"
    (out / "current_status.json").write_text(encoded, encoding="utf-8")
    (out / "current_flag.json").write_text(encoded, encoding="utf-8")
    print(slug, payload["status"], payload["flag"] or "no-explicit-flag", payload.get("explicit_flag_evidence"))


if __name__ == "__main__":
    main()
