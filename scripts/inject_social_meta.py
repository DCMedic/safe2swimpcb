from pathlib import Path
import re

SOCIAL_IMAGE = "https://knowthegulf.com/assets/images/know-the-gulf-share.PNG"
SOCIAL_ALT = "Know the Gulf beach conditions, flags and Gulf safety"
X_PROFILE = "https://x.com/knowthegulf"
X_HANDLE = "@knowthegulf"
CONTACT_EMAIL = "contact@knowthegulf.com"

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

    identity_re = re.compile(r'<script id="ktg-social-identity" type="application/ld\+json">.*?</script>', re.I | re.S)
    identity = (
        '<script id="ktg-social-identity" type="application/ld+json">'
        '{"@context":"https://schema.org","@type":"Organization","@id":"https://knowthegulf.com/#organization",'
        '"name":"Know the Gulf","url":"https://knowthegulf.com/",'
        f'"email":"mailto:{CONTACT_EMAIL}","sameAs":["{X_PROFILE}"]}}'</n        '</script>'
    )
    if identity_re.search(html):
        html = identity_re.sub(identity, html, count=1)
    else:
        html = html.replace("</head>", identity + "</head>", 1)

    footer_links = (
        f' · <a class="ktg-x-link" href="{X_PROFILE}" target="_blank" rel="noopener me">Follow @knowthegulf on X ↗</a>'
        f' · <a class="ktg-contact-link" href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>'
    )
    if 'class="ktg-contact-link"' not in html:
        footer_close = html.rfind("</footer>")
        if footer_close != -1:
            if 'class="ktg-x-link"' in html:
                html = html[:footer_close] + f' · <a class="ktg-contact-link" href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>' + html[footer_close:]
            else:
                html = html[:footer_close] + footer_links + html[footer_close:]

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
    print(f"Updated social metadata, X identity and contact email in {changed} HTML files")


if __name__ == "__main__":
    main()
