# Deploy Safe2Swim PCB to safe2swimpcb.com

## 1. Extract and publish the repository

Create a **public** GitHub repository named `safe2swimpcb` under the `DCMedic` account and push this project to the repository root. The included `deploy_windows.ps1` can create and push the repository automatically if Git and GitHub CLI are installed and authenticated.

From PowerShell in the extracted project folder:

```powershell
gh auth login
Set-ExecutionPolicy -Scope Process Bypass
.\deploy_windows.ps1
```

## 2. Enable GitHub Pages using GitHub Actions

Open **Repository → Settings → Pages**. Under **Build and deployment → Source**, choose **GitHub Actions**.

The repository includes `.github/workflows/deploy-pages.yml` for initial/manual deployments. The two data-update workflows also republish the site after they commit changed data. This is intentional: commits created by the built-in workflow `GITHUB_TOKEN` do not trigger a separate Pages build.

## 3. Verify the domain before pointing DNS

In your personal GitHub settings, open **Settings → Pages → Add a domain** and add `safe2swimpcb.com`. GitHub will show a unique TXT record such as `_github-pages-challenge-DCMedic.safe2swimpcb.com`. Add the exact TXT record/value GitHub provides at your DNS provider, then complete verification. Keep this TXT record after verification.

## 4. Configure the custom domain in the repository

Back in **Repository → Settings → Pages**, set **Custom domain** to:

```text
safe2swimpcb.com
```

The repository also contains a `CNAME` file for portability, but when publishing with a custom GitHub Actions workflow GitHub requires the custom domain to be configured in repository settings.

## 5. Configure DNS

At the DNS provider for `safe2swimpcb.com`, remove conflicting apex A/AAAA/ALIAS/ANAME records and create these four A records:

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
Resolve-DnsName safe2swimpcb.com -Type A
Resolve-DnsName www.safe2swimpcb.com -Type CNAME
Resolve-DnsName _github-pages-challenge-DCMedic.safe2swimpcb.com -Type TXT
```

## 6. Enable HTTPS

After GitHub recognizes the DNS configuration and provisions the certificate, open **Repository → Settings → Pages** and enable **Enforce HTTPS**.

## 7. Confirm Actions permissions

Open **Repository → Settings → Actions → General**. Ensure GitHub Actions is enabled. Under **Workflow permissions**, use **Read and write permissions** if the repository-level setting requires it. The Safe2Swim workflows explicitly request only the permissions they need (`contents: write`, `pages: write`, and `id-token: write`).

## 8. Run the site deployment once

Open **Actions → Deploy Safe2Swim PCB to GitHub Pages → Run workflow → main → Run workflow**. A successful run should create the `github-pages` deployment and publish the current repository contents.

## 9. Start the automated data collection

Open **Actions** and manually run both workflows once:

1. `Poll current PCB beach flag`
2. `Refresh Safe2Swim research dataset`

The first establishes a fresh live flag record and republishes the site if the cached status changes. The second enriches the historical/daily dataset and republishes any changed data.

After the first runs, `Poll current PCB beach flag` is scheduled every 30 minutes from 06:00–22:59 America/Chicago, and `Refresh Safe2Swim research dataset` runs daily at 05:23 America/Chicago.

## 10. Verify production

Check:

- `https://safe2swimpcb.com`
- `https://www.safe2swimpcb.com`
- Current flag displays a recent **Last verified by automation** timestamp.
- **Actions** shows successful runs for deployment, flag polling, and daily research refresh.
- `data/flag_observations_auto.csv` begins accumulating new observations without modifying the archive.

## 11. Data retention rule

Do not delete or rewrite `data/flag_observations_archive.csv`. Future snapshots append to `data/flag_observations_auto.csv`; master, daily, environmental, and modeling tables are reproducible derived data.
