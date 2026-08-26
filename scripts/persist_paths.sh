#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -lt 2 ]]; then
  echo "usage: $0 <commit-message> <path> [path ...]" >&2
  exit 64
fi

message="$1"
shift
paths=("$@")

git config user.name "${GIT_PERSIST_USER_NAME:-knowthegulf-data-bot}"
git config user.email "${GIT_PERSIST_USER_EMAIL:-actions@users.noreply.github.com}"

git add -- "${paths[@]}"
if git diff --cached --quiet; then
  echo "No owned-path changes to persist."
  exit 0
fi

git commit -m "$message"

# All production data workflows write to the same main ref even when their files
# do not overlap. GitHub rejects a non-fast-forward push if another healthy lane
# advances main between checkout and push. Rebase the already-validated commit
# onto the newest main and retry. A real content conflict is intentionally fatal:
# it indicates overlapping file ownership and must not be auto-resolved.
for attempt in $(seq 1 12); do
  git fetch origin main

  if ! git rebase origin/main; then
    git rebase --abort 2>/dev/null || true
    echo "Persistence conflict while rebasing owned paths onto latest main." >&2
    git status --short >&2 || true
    exit 2
  fi

  if git push origin HEAD:main; then
    echo "Persistence succeeded on attempt $attempt."
    exit 0
  fi

  if [[ "$attempt" -eq 12 ]]; then
    echo "Failed to persist after 12 main-ref contention retries." >&2
    exit 1
  fi

  sleep $((1 + (attempt % 4)))
done
