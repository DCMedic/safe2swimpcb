from pathlib import Path
import re

SOCIAL_IMAGE = "https://knowthegulf.com/assets/images/know-the-gulf-share.PNG"
SOCIAL_ALT = "Know the Gulf beach conditions, flags and Gulf safety"

OG_IMAGE_RE = re.compile(r'<meta\s+property=["\']og:image["\']\s+content=["\'][^"\']*["\']\s*/?>', re.I)
OG_ALT_RE = re.compile(r'<meta\s+property=["\']og:image:alt["\']\s+content=["\'][^"\']*["\']\s*/?>', re.I)
TW_IMAGE_RE = re.compile(r'<meta\s+name=["\']twitter:image["\']\s+content=["\'][^"\']*["\']\s*/?>', re.I)
TW_ALT_RE = re.compile(r'<meta\s+name=["\']twitter:image:alt["\']\s+content=["\'][^"\']*["\']\s*/?>', re.I)


def inject_or_replace(html: str) -> str:
    og_image = f'<meta property="og:image" content="{SOCIAL_IMAGE}">'
    og_alt = f'<meta property="og:image:alt" content="{SOCIAL_ALT}">'
    tw_image = f'<meta name="twitter:image" content="{SOCIAL_IMAGE}">'
    tw_alt = f'<meta name="twitter:image:alt" content="{SOCIAL_ALT}">'

    if OG_IMAGE_RE.search(html):
        html = OG_IMAGE_RE.sub(og_image, html, count=1)
    else:
        html = html.replace("</head>", og_image + "</head>", 1)

    if OG_ALT_RE.search(html):
        html = OG_ALT_RE.sub(og_alt, html, count=1)
    else:
        html = html.replace("</head>", og_alt + "</head>", 1)

    if TW_IMAGE_RE.search(html):
        html = TW_IMAGE_RE.sub(tw_image, html, count=1)
    else:
        html = html.replace("</head>", tw_image + "</head>", 1)

    if TW_ALT_RE.search(html):
        html = TW_ALT_RE.sub(tw_alt, html, count=1)
    else:
        html = html.replace("</head>", tw_alt + "</head>", 1)

    return html


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    changed = 0
    for path in root.rglob("*.html"):
        if ".git" in path.parts:
            continue
        original = path.read_text(encoding="utf-8")
        updated = inject_or_replace(original)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed += 1
    print(f"Updated social image metadata in {changed} HTML files")


if __name__ == "__main__":
    main()
