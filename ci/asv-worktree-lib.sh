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
# ``snapshot_results_for_ci`` copies result files (excluding ``.git``) to
# ``ARTIFACT_RESULTS_DIR`` (default ``$REPO_ROOT/.asv/ci-artifacts``) so CI
# can upload them after the worktree is removed.
#
# ``fetch_branch`` force-updates the local branch ref from the remote
# (the orphan branch is append-only in normal use, but ``+`` is defensive
# against history rewrites). Returns 0 if a fetch happened, 1 if the
# remote does not have the branch.
#
# ``make_current_branch_config`` writes a temp asv config pinned to the
# current branch, for callers that want asv to operate on it instead of
# the branch list committed in ``asv.conf.json``. Unrelated to the
# worktree helpers but shared by the same callers; see its own comment.

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

# Copy ASV result files out of the results worktree. CI uploads this snapshot
# after ``git worktree remove`` deletes ``.asv/results/``.
snapshot_results_for_ci() {
    local src="${RESULTS_DIR:-}"
    local dest="${ARTIFACT_RESULTS_DIR:-${REPO_ROOT:+$REPO_ROOT/.asv/ci-artifacts}}"
    [ -n "$src" ] && [ -d "$src" ] || return 0
    [ -n "$dest" ] || return 0
    if [ -z "$(find "$src" -mindepth 1 -maxdepth 1 ! -name .git -print -quit)" ]; then
        return 0
    fi
    rm -rf "$dest"
    mkdir -p "$dest"
    tar -C "$src" --exclude='.git' -cf - . | tar -C "$dest" -xf -
}

# Write a temp asv config to ``$1`` whose ``branches`` field contains only
# the current branch. Used by callers that want ``asv run`` / ``asv publish``
# to operate on the current branch instead of whatever ``asv.conf.json``
# pins (typically ``master``). Caller is responsible for cleaning up the
# temp file. Must be invoked from REPO_ROOT (where ``asv.conf.json`` lives).
make_current_branch_config() {
    local out_path="$1"
    local current_branch
    current_branch="$(git rev-parse --abbrev-ref HEAD)"
    # Guard against asv.conf.json being reformatted to a multi-line
    # `branches` array, which would silently leave the sed below as a no-op
    # and emit a config still pinned to whatever asv.conf.json declares.
    if ! grep -qE '"branches": \[[^]]*\]' asv.conf.json; then
        echo "Error: asv.conf.json does not contain a single-line 'branches' array; make_current_branch_config cannot patch it" >&2
        return 1
    fi
    sed "s|\"branches\": \[[^]]*\]|\"branches\": [\"$current_branch\"]|" \
        asv.conf.json > "$out_path"
}
