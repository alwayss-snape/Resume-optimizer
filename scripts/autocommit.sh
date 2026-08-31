#!/usr/bin/env bash
# Simple helper to commit all changes and push to current branch every N seconds.
# Intended for manual execution by the developer in their local environment.
# Usage: ./scripts/autocommit.sh 300 "Auto-commit: progress"

INTERVAL=${1:-300}
MSG=${2:-"Auto-commit: periodic checkpoint"}

set -euo pipefail

while true; do
  git add -A
  git commit -m "$MSG" || true
  git push || true
  sleep "$INTERVAL"
done
