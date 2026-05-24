#!/bin/sh
# Select the two commits used by the merge-request ASV regression gate.
#
# Source this script from the GitLab CI job. It exports:
#   ASV_BASE - the current target-branch commit
#   ASV_HEAD - the proposed merge commit to benchmark against ASV_BASE
set -eu

: "${CI_MERGE_REQUEST_TARGET_BRANCH_NAME:?}"
: "${CI_COMMIT_SHA:?}"

ASV_TARGET_REMOTE="${ASV_TARGET_REMOTE:-origin}"
ASV_MERGE_BRANCH="${ASV_MERGE_BRANCH:-asv-proposed-merge}"

git fetch "$ASV_TARGET_REMOTE" "$CI_MERGE_REQUEST_TARGET_BRANCH_NAME"

# Prefer GitLab's target-branch SHA when present so the comparison matches the
# MR pipeline snapshot. Fall back to FETCH_HEAD for CI contexts that only give
# us the fetched target branch.
if [ -n "${CI_MERGE_REQUEST_TARGET_BRANCH_SHA:-}" ]; then
    ASV_BASE="$CI_MERGE_REQUEST_TARGET_BRANCH_SHA"
else
    ASV_BASE="$(git rev-parse FETCH_HEAD)"
fi
git rev-parse --verify "$ASV_BASE^{commit}" >/dev/null

# Merged-result and merge-train pipelines are already checked out at GitLab's
# proposed merge commit. Detached MR pipelines are checked out at the source
# branch tip, so synthesize the proposed merge commit locally from ASV_BASE.
case "${CI_MERGE_REQUEST_EVENT_TYPE:-detached}" in
    merged_result | merge_train)
        ASV_HEAD="$CI_COMMIT_SHA"
        ;;
    *)
        ASV_SOURCE_SHA="${ASV_SOURCE_SHA:-${CI_MERGE_REQUEST_SOURCE_BRANCH_SHA:-$CI_COMMIT_SHA}}"
        git rev-parse --verify "$ASV_SOURCE_SHA^{commit}" >/dev/null
        git checkout -B "$ASV_MERGE_BRANCH" "$ASV_BASE"
        git \
            -c user.name="${GIT_AUTHOR_NAME:-PsyNet CI}" \
            -c user.email="${GIT_AUTHOR_EMAIL:-ci@psynet.dev}" \
            merge --no-ff --no-edit "$ASV_SOURCE_SHA"
        ASV_HEAD="$(git rev-parse HEAD)"
        ;;
esac

git rev-parse --verify "$ASV_HEAD^{commit}" >/dev/null
export ASV_BASE ASV_HEAD

echo "Comparing benchmark base $ASV_BASE -> proposed merge $ASV_HEAD"
