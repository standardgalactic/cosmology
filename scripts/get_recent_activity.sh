#!/usr/bin/env bash
#
# get_recent_activity.sh
#
# Show recent commits with the files changed in each commit.
#
# Usage:
#   ./get_recent_activity.sh
#   ./get_recent_activity.sh 20
#

set -euo pipefail

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Error: not inside a Git repository." >&2
    exit 1
fi

COUNT="${1:-10}"

if ! [[ "$COUNT" =~ ^[0-9]+$ ]] || [[ "$COUNT" -eq 0 ]]; then
    echo "Usage: $0 [positive-commit-count]" >&2
    exit 1
fi

git log \
    --max-count="$COUNT" \
    --date=short \
    --pretty=format:'COMMIT %h%nDATE   %ad%nAUTHOR %an%nSUBJECT %s' \
    --name-status
