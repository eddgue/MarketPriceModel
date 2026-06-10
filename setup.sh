#!/usr/bin/env bash
# One-shot deploy: GitHub repo + Pages + weekly USDA refresh.
# Usage: bash setup.sh [repo-name]
# Needs: gh (GitHub CLI) and git, both standard in code sessions.
set -euo pipefail

REPO="${1:-produce-data-view}"

command -v gh >/dev/null || { echo "gh CLI not found. Use the manual steps in README.md."; exit 1; }
gh auth status >/dev/null 2>&1 || gh auth login

if [ -z "${MARS_API_KEY:-}" ]; then
  printf "MARS API key (input hidden; free at mymarketnews.ams.usda.gov/mymarketnews-api): "
  read -rs MARS_API_KEY; echo
fi
[ -n "$MARS_API_KEY" ] || { echo "No key given."; exit 1; }

OWNER="$(gh api user -q .login)"

git init -q 2>/dev/null || true
git config user.name  >/dev/null 2>&1 || git config user.name "$OWNER"
git config user.email >/dev/null 2>&1 || git config user.email "$OWNER@users.noreply.github.com"
git add -A
git commit -qm "initial deploy" 2>/dev/null || true
git branch -M main

if git remote get-url origin >/dev/null 2>&1; then
  git push -u origin main
else
  gh repo create "$REPO" --public --source=. --remote=origin --push
fi

gh secret set MARS_API_KEY --body "$MARS_API_KEY" --repo "$OWNER/$REPO"

gh api "repos/$OWNER/$REPO/pages" -X POST \
  -f 'source[branch]=main' -f 'source[path]=/' >/dev/null 2>&1 \
  || echo "Pages already enabled or pending."

sleep 5
gh workflow run usda-refresh --repo "$OWNER/$REPO" 2>/dev/null \
  || echo "Workflow not registered yet; trigger it once from the Actions tab."

echo
echo "Done. Watch the first data pull:  gh run watch --repo $OWNER/$REPO"
echo "Live page in a minute or two:     https://$OWNER.github.io/$REPO/"
echo "Refresh runs Tuesday evenings US Central, automatic."
