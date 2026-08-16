from pathlib import Path
import re

SOCIAL_IMAGE = "https://knowthegulf.com/assets/images/know-the-gulf-share.PNG"
SOCIAL_ALT = "Know the Gulf beach conditions, flags and Gulf safety"
X_PROFILE = "https://x.com/knowthegulf"
X_HANDLE = "@knowthegulf"

OG_IMAGE_RE = re.compile(r'<meta\s+property=["\']og:image["\']\s+content=["\'][^"\']*["\']\s*/?>', re.I)
OG_ALT_RE = re.compile(r'<meta\s+property=["\']og:image:alt["\']\s+content=["\'][^"\']*["\']\s*/?>', re.I)
TW_IMAGE_RE = re.compile(r'<meta\s+name=["\']twitter:image["\']\s+content=["\'][^"\']*["\']\s*/?>', re.I)
TW_ALT_RE = re.compile(r'<meta\s+name=["\']twitter:image:alt["\']\s+content=["\'][^"\']*["\']\s*/?>', re.I)
TW_SITE_RE = re.compile(r'<meta\s+name=["\']twitter:site["\']\s+content=["\'][^"\']*["\']\s*/?>', re.I)


def inject_or_replace(html: str) -> str:
    tags = [
        (OG_IMAGE_RE, f'<meta property="og:image" content="{SOCIAL_IMAGE}">'),
        (OG_ALT_RE, f'<meta property="og:image:alt" content="{SOCIAL_ALT}">'),
        (TW_IMAGE_RE, f'<meta name="twitter:image" content="{SOCIAL_IMAGE}">'),
        (TW_ALT_RE, f'<meta name="twitter:image:alt" content="{SOCIAL_ALT}">'),
        (TW_SITE_RE, f'<meta name="twitter:site" content="{X_HANDLE}">'),
    ]
    for pattern, tag in tags:
        if pattern.search(html):
            html = pattern.sub(tag, html, count=1)
        else:
            html = html.replace("</head>", tag + "</head>", 1)

    if 'id="ktg-social-identity"' not in html:
        identity = (
            '<script id="ktg-social-identity" type="application/ld+json">'
            '{"@context":"https://schema.org","@type":"Organization","@id":"https://knowthegulf.com/#organization",'
            '"name":"Know the Gulf","url":"https://knowthegulf.com/",'
            '"sameAs":["https://x.com/knowthegulf"]}</script>'
        )
        html = html.replace("</head>", identity + "</head>", 1)

    if 'class="ktg-x-link"' not in html:
        link = f' · <a class="ktg-x-link" href="{X_PROFILE}" target="_blank" rel="noopener me">Follow @knowthegulf on X ↗</a>'
        footer_close = html.rfind("</footer>")
        if footer_close != -1:
            html = html[:footer_close] + link + html[footer_close:]

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
    print(f"Updated social metadata and X identity in {changed} HTML files")


if __name__ == "__main__":
    main()
