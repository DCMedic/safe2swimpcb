# Know the Gulf edge infrastructure

This directory contains production-ready edge configuration for the next hosting layer in front of Know the Gulf.

## Purpose

The current GitHub Pages deployment cannot control all HTTP response headers or cache policy. The September 1, 2026 mobile Lighthouse report reached 97/100 performance and 100/100 for Accessibility, Best Practices, and SEO, leaving the remaining meaningful findings at the hosting layer.

The Caddy configuration in `infra/caddy/Caddyfile` provides:

- automatic HTTPS and HTTP/2/HTTP/3 support;
- HSTS;
- Cross-Origin-Opener-Policy;
- clickjacking protection through both `X-Frame-Options` and HTTP CSP `frame-ancestors`;
- MIME-sniffing protection;
- a strict referrer policy;
- a conservative Permissions Policy;
- gzip and Zstandard compression;
- explicit no-store rules for current safety/health JSON;
- bounded caching for static assets; and
- permanent `www` → apex canonical redirects.

## Safety rule for live data

Never apply long-lived caching to `current_flag.json` files or workflow/publisher health state. Current beach-safety state must remain freshness-first.

## Trusted Types

Trusted Types is intentionally **not** enforced yet. The current frontend uses DOM APIs such as `innerHTML`; enabling `require-trusted-types-for 'script'` without first migrating those sinks would risk breaking production. This is tracked as a future application-hardening task, not a header to enable blindly.

## Deployment model

The preferred VPS layout is:

```text
/srv/knowthegulf/
├── releases/
│   └── <release-id>/
└── current -> releases/<release-id>
```

Deploy into a new release directory, validate it, then atomically repoint `current`. Do not edit the live release in place.

## Activation

These files do not change the current GitHub Pages production path by themselves. Activate them only after a VPS or equivalent configurable edge is provisioned and tested on a staging hostname. DNS should move only after HTTPS, routes, JSON freshness behavior, redirects, and rollback are verified.
