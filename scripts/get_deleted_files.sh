#!/usr/bin/env bash
#
# git-deleted-files.sh
#
# Find files that were deleted anywhere in Git history.
#
# Usage:
#   ./git-deleted-files.sh
#   ./git-deleted-files.sh --all
#   ./git-deleted-files.sh --unique
#   ./git-deleted-files.sh --recover <path>
#

set -euo pipefail

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Error: not inside a Git repository." >&2
    exit 1
fi

MODE="${1:---all}"

case "$MODE" in

    --all)
        echo "Deleted files in Git history:"
        echo

        git log \
            --all \
            --diff-filter=D \
            --summary \
            --format='COMMIT %H%nDATE   %ad%nAUTHOR %an%nSUBJECT %s' \
            --date=short

        ;;

    --unique)
        echo "Files that have been deleted at least once:"
        echo

        git log \
            --all \
            --diff-filter=D \
            --name-only \
            --format='' |
        sed '/^$/d' |
        sort -u

        ;;

    --recover)
        if [[ $# -lt 2 ]]; then
            echo "Usage: $0 --recover <path>" >&2
            exit 1
        fi

        FILE="$2"

        COMMIT="$(
            git log \
                --all \
                --diff-filter=D \
                --format='%H' \
                -- "$FILE" |
            head -n 1
        )"

        if [[ -z "$COMMIT" ]]; then
            echo "No deletion found for:"
            printf '  %s\n' "$FILE"
            exit 1
        fi

        PARENT="${COMMIT}^"

        echo "Deletion commit:"
        git show \
            --no-patch \
            --format='%H%n%ad%n%an%n%s' \
            --date=iso \
            "$COMMIT"

        echo
        echo "File existed immediately before deletion at:"
        echo "  $PARENT:$FILE"
        echo
        echo "To inspect it:"
        printf "  git show '%s:%s'\n" "$PARENT" "$FILE"
        echo
        echo "To restore it into your working tree:"
        printf "  git restore --source='%s' -- '%s'\n" "$PARENT" "$FILE"

        ;;

    *)
        echo "Usage:"
        echo "  $0 --all"
        echo "  $0 --unique"
        echo "  $0 --recover <path>"
        exit 1
        ;;
esac
