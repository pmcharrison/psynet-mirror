# Shared helpers for mounting the `benchmark-results` orphan branch as a
# git worktree. Source this from another script (do not run it directly).
#
# The caller must set:
#     RESULTS_DIR — absolute path where the worktree should live
#     BRANCH      — branch name to check out (typically "benchmark-results")
#     REMOTE      — remote name for ``fetch_branch`` (typically "origin")
#
# After ``attach_worktree``, ATTACHED=1 means this caller attached (or
# adopted) the worktree and is responsible for releasing it via
# ``detach_worktree``. ``detach_worktree`` runs ``git worktree remove``,
# which preserves the worktree if it has uncommitted changes (so failed
# benchmark runs leave their state behind for inspection).
#
# ``fetch_branch`` force-updates the local branch ref from the remote
# (the orphan branch is append-only in normal use, but ``+`` is defensive
# against history rewrites). Returns 0 if a fetch happened, 1 if the
# remote does not have the branch.

fetch_branch() {
    if git ls-remote --exit-code --heads "$REMOTE" "$BRANCH" >/dev/null 2>&1; then
        echo "Fetching latest $BRANCH from $REMOTE..."
        git fetch "$REMOTE" "+$BRANCH:$BRANCH"
        return 0
    fi
    return 1
}

attach_worktree() {
    git worktree prune
    if [ -e "$RESULTS_DIR/.git" ]; then
        local current
        current=$(git -C "$RESULTS_DIR" rev-parse --abbrev-ref HEAD)
        if [ "$current" = "HEAD" ]; then
            echo "Error: $RESULTS_DIR is in detached-HEAD state, expected branch '$BRANCH'" >&2
            exit 1
        fi
        if [ "$current" != "$BRANCH" ]; then
            echo "Error: $RESULTS_DIR is checked out to '$current', expected '$BRANCH'" >&2
            exit 1
        fi
        ATTACHED=1
        return
    fi
    if [ -e "$RESULTS_DIR" ]; then
        rm -rf "$RESULTS_DIR"
    fi
    mkdir -p "$(dirname "$RESULTS_DIR")"
    git worktree add "$RESULTS_DIR" "$BRANCH"
    ATTACHED=1
}

detach_worktree() {
    [ "${ATTACHED:-0}" = "1" ] || return 0
    if [ -e "$RESULTS_DIR/.git" ]; then
        if ! git worktree remove "$RESULTS_DIR" 2>/dev/null; then
            echo "Worktree at $RESULTS_DIR has uncommitted changes; leaving in place" >&2
            echo "Inspect with: git -C $RESULTS_DIR status" >&2
        fi
    fi
}
