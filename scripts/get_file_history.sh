#!/usr/bin/env bash
#
# get_file_history.sh
#
# Show the full change history for a file path, including renames.
#
# Usage:
#   ./get_file_history.sh <path>
#

set -euo pipefail

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Error: not inside a Git repository." >&2
    exit 1
fi

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <path>" >&2
    exit 1
fi

TARGET="$1"

git log \
    --follow \
    --date=short \
    --format='COMMIT %H%nDATE   %ad%nAUTHOR %an%nSUBJECT %s' \
    --name-status \
    -- "$TARGET"
