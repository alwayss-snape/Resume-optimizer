#!/usr/bin/env bash
# One-time setup per clone: point git at the versioned hooks in .githooks/,
# which keep docs/KNOWLEDGE_GRAPH.* and docs/CHANGE_LOG.md up to date on commit.
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
chmod +x "$ROOT"/.githooks/*
git -C "$ROOT" config core.hooksPath .githooks
echo "Hooks installed (core.hooksPath=.githooks)."
