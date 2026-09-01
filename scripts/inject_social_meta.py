from pathlib import Path
import base64
import hashlib
import re

SOCIAL_IMAGE = "https://knowthegulf.com/assets/images/know-the-gulf-share.PNG"
SOCIAL_ALT = "Know the Gulf beach conditions, flags and Gulf safety"
X_PROFILE = "https://x.com/knowthegulf"
X_HANDLE = "@knowthegulf"
CONTACT_EMAIL = "contact@knowthegulf.com"
SITE_UI = '<script defer src="/assets/site-ui.js"></script>'
REFERRER_META = '<meta name="referrer" content="strict-origin-when-cross-origin">'

OG_IMAGE_RE = re.compile(r'<meta\s+property=["\']og:image["\']\s+content=["\'][^"\']*["\']\s*/?>', re.I)
OG_ALT_RE = re.compile(r'<meta\s+property=["\']og:image:alt["\']\s+content=["\'][^"\']*["\']\s*/?>', re.I)
TW_IMAGE_RE = re.compile(r'<meta\s+name=["\']twitter:image["\']\s+content=["\'][^"\']*["\']\s*/?>', re.I)
TW_ALT_RE = re.compile(r'<meta\s+name=["\']twitter:image:alt["\']\s+content=["\'][^"\']*["\']\s*/?>', re.I)
TW_SITE_RE = re.compile(r'<meta\s+name=["\']twitter:site["\']\s+content=["\'][^"\']*["\']\s*/?>', re.I)
IDENTITY_RE = re.compile(r'<script id="ktg-social-identity" type="application/ld\+json">.*?</script>', re.I | re.S)
SITE_UI_RE = re.compile(r'<script[^>]+src=["\']/assets/site-ui\.js["\'][^>]*></script>', re.I)
CSP_RE = re.compile(r'<meta\s+http-equiv=["\']Content-Security-Policy["\'][^>]*>', re.I)
REFERRER_RE = re.compile(r'<meta\s+name=["\']referrer["\'][^>]*>', re.I)
INLINE_SCRIPT_RE = re.compile(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', re.I | re.S)


def content_security_policy(html: str) -> str:
    hashes = []
    for body in INLINE_SCRIPT_RE.findall(html):
        digest = base64.b64encode(hashlib.sha256(body.encode("utf-8")).digest()).decode("ascii")
        hashes.append(f"'sha256-{digest}'")
    script_src = " ".join(["'self'", "https://cdn.jsdelivr.net", *dict.fromkeys(hashes)])
    return (
        "default-src 'self'; "
        f"script-src {script_src}; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https:; "
        "font-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "upgrade-insecure-requests"
    )


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

    identity = (
        '<script id="ktg-social-identity" type="application/ld+json">'
        '{"@context":"https://schema.org","@type":"Organization","@id":"https://knowthegulf.com/#organization",'
        '"name":"Know the Gulf","url":"https://knowthegulf.com/",'
        f'"email":"mailto:{CONTACT_EMAIL}","sameAs":["{X_PROFILE}"]}}'
        '</script>'
    )
    if IDENTITY_RE.search(html):
        html = IDENTITY_RE.sub(identity, html, count=1)
    else:
        html = html.replace("</head>", identity + "</head>", 1)

    if not SITE_UI_RE.search(html):
        html = html.replace("</head>", SITE_UI + "</head>", 1)

    if REFERRER_RE.search(html):
        html = REFERRER_RE.sub(REFERRER_META, html, count=1)
    else:
        html = html.replace("</head>", REFERRER_META + "</head>", 1)

    csp_tag = f'<meta http-equiv="Content-Security-Policy" content="{content_security_policy(html)}">'
    if CSP_RE.search(html):
        html = CSP_RE.sub(csp_tag, html, count=1)
    else:
        html = html.replace("</head>", csp_tag + "</head>", 1)

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
    print(f"Updated shared UI/social metadata in {changed} HTML files")


if __name__ == "__main__":
    main()
