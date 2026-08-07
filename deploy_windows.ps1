$ErrorActionPreference = "Stop"
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "Git is required." }
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw "GitHub CLI (gh) is required. Install it, then run: gh auth login" }
gh auth status
if (-not (Test-Path .git)) { git init; git branch -M main }
git add .
$changes = git status --porcelain
if ($changes) { git commit -m "Initial Safe2Swim PCB production site" }
$remote = git remote get-url origin 2>$null
if (-not $remote) {
  gh repo create DCMedic/safe2swimpcb --public --source . --remote origin --push
} else {
  git push -u origin main
}
Write-Host "Repository pushed. Next: GitHub repository Settings -> Pages -> Source: GitHub Actions, then verify/configure safe2swimpcb.com. See DEPLOYMENT.md."
