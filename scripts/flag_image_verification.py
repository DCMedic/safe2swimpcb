#!/usr/bin/env python3
from __future__ import annotations

import colorsys
import io
import re
from dataclasses import asdict, dataclass

import cairosvg
import requests
from PIL import Image

USER_AGENT = "KnowTheGulf/1.0 (+https://knowthegulf.com)"
MAX_IMAGE_BYTES = 5_000_000
MIN_PRIMARY_FRACTION = 0.18
MIN_PRIMARY_PURITY = 0.72
MIN_PURPLE_FRACTION = 0.08
MIN_BBOX_FILL = 0.30
SVG_EXTERNAL_REFERENCE = re.compile(
    rb"(?:<\s*image\b|\b(?:href|xlink:href)\s*=\s*['\"]\s*(?:https?:|//|file:|ftp:|data:)|url\s*\(\s*['\"]?\s*(?:https?:|//|file:|ftp:|data:))",
    re.I,
)


@dataclass(frozen=True)
class ImageFlagResult:
    primary: str | None
    purple: bool
    confidence: float
    publishable: bool
    reason: str
    color_fractions: dict[str, float]
    bbox_fill: float

    def to_dict(self) -> dict:
        return asdict(self)


def _hue_bucket(r: int, g: int, b: int) -> str | None:
    rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
    h, s, v = colorsys.rgb_to_hsv(rf, gf, bf)
    if s < 0.42 or v < 0.24 or v > 0.98:
        return None
    deg = h * 360.0
    if deg <= 18 or deg >= 342:
        return "red"
    if 38 <= deg <= 72:
        return "yellow"
    if 78 <= deg <= 165:
        return "green"
    if 255 <= deg <= 325:
        return "purple"
    return None


def _bbox_fill(mask_points: list[tuple[int, int]]) -> float:
    if not mask_points:
        return 0.0
    xs = [p[0] for p in mask_points]
    ys = [p[1] for p in mask_points]
    area = (max(xs) - min(xs) + 1) * (max(ys) - min(ys) + 1)
    return len(mask_points) / area if area else 0.0


def _looks_like_svg(data: bytes) -> bool:
    head = data[:4096].lstrip().lower()
    return head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in head)


def _decode_image(data: bytes) -> Image.Image:
    if _looks_like_svg(data):
        # Current-condition SVGs are accepted only when self-contained. This keeps
        # vector rasterization from following network/file/data references hidden
        # inside an otherwise trusted official SVG asset. Standard namespace URLs
        # remain valid because only resource-bearing attributes/elements are gated.
        if SVG_EXTERNAL_REFERENCE.search(data):
            raise ValueError("SVG contains an external or embedded resource reference")
        png = cairosvg.svg2png(bytestring=data, output_width=400)
        return Image.open(io.BytesIO(png)).convert("RGB")
    image = Image.open(io.BytesIO(data)).convert("RGB")
    image.thumbnail((400, 400))
    return image


def classify_flag_image_bytes(data: bytes) -> ImageFlagResult:
    if not data or len(data) > MAX_IMAGE_BYTES:
        return ImageFlagResult(None, False, 0.0, False, "image missing or exceeds size limit", {}, 0.0)
    try:
        image = _decode_image(data)
    except Exception as exc:
        reason = str(exc).strip() or "image could not be decoded"
        if "SVG contains" not in reason:
            reason = "image could not be decoded"
        return ImageFlagResult(None, False, 0.0, False, reason, {}, 0.0)

    width, height = image.size
    total = max(width * height, 1)
    counts = {"red": 0, "yellow": 0, "green": 0, "purple": 0}
    points = {key: [] for key in counts}
    for y in range(height):
        for x in range(width):
            bucket = _hue_bucket(*image.getpixel((x, y)))
            if bucket:
                counts[bucket] += 1
                points[bucket].append((x, y))

    fractions = {k: round(v / total, 4) for k, v in counts.items()}
    primary_colors = {k: counts[k] for k in ("red", "yellow", "green")}
    winner = max(primary_colors, key=primary_colors.get)
    winner_fraction = primary_colors[winner] / total
    primary_colored = sum(primary_colors.values())
    purity = primary_colors[winner] / primary_colored if primary_colored else 0.0
    fill = _bbox_fill(points[winner])
    purple = counts["purple"] / total >= MIN_PURPLE_FRACTION and _bbox_fill(points["purple"]) >= 0.22

    confidence = round(min(1.0, (winner_fraction / MIN_PRIMARY_FRACTION) * 0.45 + purity * 0.35 + min(fill / MIN_BBOX_FILL, 1.0) * 0.20), 3)
    if winner_fraction < MIN_PRIMARY_FRACTION:
        return ImageFlagResult(None, purple, confidence, False, "no primary flag color occupies enough of the eligible image", fractions, round(fill, 3))
    if purity < MIN_PRIMARY_PURITY:
        return ImageFlagResult(None, purple, confidence, False, "multiple primary colors make the eligible image ambiguous", fractions, round(fill, 3))
    if fill < MIN_BBOX_FILL:
        return ImageFlagResult(None, purple, confidence, False, "dominant color is too fragmented to resemble a flag region", fractions, round(fill, 3))
    if winner == "red":
        return ImageFlagResult(None, purple, confidence, False, "red is visually present but image pixels alone cannot distinguish Single Red from Double Red", fractions, round(fill, 3))

    primary = "Yellow" if winner == "yellow" else "Green"
    return ImageFlagResult(primary, purple, confidence, confidence >= 0.82, "high-confidence eligible current-status image" if confidence >= 0.82 else "visual confidence below publication threshold", fractions, round(fill, 3))


def fetch_and_classify_flag_image(url: str, session: requests.Session | None = None) -> tuple[ImageFlagResult | None, str | None]:
    s = session or requests.Session()
    s.headers.setdefault("User-Agent", USER_AGENT)
    try:
        r = s.get(url, timeout=(5, 20))
        r.raise_for_status()
    except requests.RequestException as exc:
        return None, str(exc)
    content_type = (r.headers.get("content-type") or "").lower()
    if content_type and "image" not in content_type:
        return None, f"candidate did not return an image content type: {content_type}"
    return classify_flag_image_bytes(r.content), None
