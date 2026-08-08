# Deploy Know the Gulf to knowthegulf.com

## 1. Repository

The production repository remains `DCMedic/safe2swimpcb` so existing automation, history, and links do not need to be disrupted during the brand migration. The public product name is **Know the Gulf** and the canonical domain is **knowthegulf.com**.

## 2. Enable GitHub Pages using GitHub Actions

Open **Repository → Settings → Pages**. Under **Build and deployment → Source**, choose **GitHub Actions**.

The repository includes `.github/workflows/deploy-pages.yml` for deployments. The data-update workflows also republish the site after they commit changed data. This is intentional: commits created by the built-in workflow `GITHUB_TOKEN` do not trigger a separate Pages build.

## 3. Verify knowthegulf.com before pointing DNS

In your personal GitHub settings, open **Settings → Pages → Add a domain** and add `knowthegulf.com`. GitHub will show a unique TXT record such as `_github-pages-challenge-DCMedic.knowthegulf.com`. Add the exact TXT record/value GitHub provides at your DNS provider, then complete verification. Keep the TXT record after verification.

## 4. Configure the custom domain in the repository

Back in **Repository → Settings → Pages**, set **Custom domain** to:

```text
knowthegulf.com
```

The repository contains a `CNAME` file with the same domain. When publishing with a GitHub Actions workflow, also keep the domain configured in repository settings.

## 5. Configure DNS for knowthegulf.com

At the DNS provider for `knowthegulf.com`, remove conflicting apex A/AAAA/ALIAS/ANAME records and create these four GitHub Pages A records:

| Type | Host | Value |
|---|---|---|
| A | @ | 185.199.108.153 |
| A | @ | 185.199.109.153 |
| A | @ | 185.199.110.153 |
| A | @ | 185.199.111.153 |

Optional IPv6 AAAA records:

- `2606:50c0:8000::153`
- `2606:50c0:8001::153`
- `2606:50c0:8002::153`
- `2606:50c0:8003::153`

Create the `www` CNAME:

| Type | Host | Value |
|---|---|---|
| CNAME | www | DCMedic.github.io |

Do **not** use a wildcard `*` DNS record for this site.

On Windows you can verify DNS with:

```powershell
Resolve-DnsName knowthegulf.com -Type A
Resolve-DnsName www.knowthegulf.com -Type CNAME
Resolve-DnsName _github-pages-challenge-DCMedic.knowthegulf.com -Type TXT
```

## 6. Enable HTTPS

After GitHub recognizes the DNS configuration and provisions the certificate, open **Repository → Settings → Pages** and enable **Enforce HTTPS**.

## 7. Configure the secondary domains as permanent redirects

`knowthegulf.org` and `safe2swimpcb.com` should **not** host duplicate copies of the site. Configure them at their DNS/registrar/hosting provider to issue HTTP **301 permanent redirects** to the canonical `.com` domain while preserving the path and query string whenever the provider supports it.

Recommended behavior:

```text
https://knowthegulf.org/*  →  https://knowthegulf.com/$1
https://www.knowthegulf.org/*  →  https://knowthegulf.com/$1
https://safe2swimpcb.com/*  →  https://knowthegulf.com/$1
https://www.safe2swimpcb.com/*  →  https://knowthegulf.com/$1
```

This preserves legacy bookmarks, old QR codes, inbound links, and as much search equity as possible. Do not use JavaScript or meta-refresh redirects when an HTTP 301 is available.

## 8. Confirm Actions permissions

Open **Repository → Settings → Actions → General**. Ensure GitHub Actions is enabled. Under **Workflow permissions**, use **Read and write permissions** if the repository-level setting requires it. The workflows explicitly request only the permissions they need (`contents: write`, `pages: write`, and `id-token: write`).

## 9. Run the site deployment once

Open **Actions → Deploy Know the Gulf to GitHub Pages → Run workflow → main → Run workflow**. A successful run should create the `github-pages` deployment and publish the current repository contents.

## 10. Start or confirm automated data collection

Open **Actions** and manually run both workflows once after the migration:

1. `Poll current PCB beach flag`
2. `Refresh Know the Gulf research dataset`

The first establishes a fresh live flag record and republishes the site if the cached status changes. The second enriches the historical/daily dataset and republishes any changed data.

After the first runs, `Poll current PCB beach flag` is scheduled every 30 minutes from 06:00–22:59 America/Chicago, and the research refresh runs daily at 05:23 America/Chicago.

## 11. Verify production

Check:

- `https://knowthegulf.com`
- `https://www.knowthegulf.com`
- `https://knowthegulf.org` redirects permanently to `https://knowthegulf.com/`
- `https://safe2swimpcb.com` redirects permanently to `https://knowthegulf.com/`
- Current flag displays a recent **Last verified by automation** timestamp.
- **Actions** shows successful runs for deployment, flag polling, and daily research refresh.
- `data/flag_observations_auto.csv` continues accumulating observations without modifying the immutable archive.

## 12. Search migration

After the new domain is live and redirects are active:

1. Add and verify `https://knowthegulf.com/` in Google Search Console.
2. Submit `https://knowthegulf.com/sitemap.xml`.
3. Keep the old `safe2swimpcb.com` Search Console property verified.
4. Use Google Search Console's **Change of Address** workflow for the old domain if available for the property type.
5. Request indexing for the new homepage and the five Panama City Beach guide URLs.
6. Do not remove the old-domain redirects after indexing; keep them indefinitely.

## 13. Data retention rule

Do not delete or rewrite `data/flag_observations_archive.csv`. Historical records may contain legacy Safe2Swim source labels because those labels are part of the provenance at the time the observation was collected. Future product-facing labels use Know the Gulf. Master, daily, environmental, and modeling tables remain reproducible derived data.
