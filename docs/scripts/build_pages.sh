#!/usr/bin/env bash
# Build the multi-version PsyNet docs site for GitLab Pages publishing.
#
# Modes (selected by CI environment):
# - Branch pipeline (no $CI_COMMIT_TAG): full rebuild — highest stable to
#   public/, selected (major,minor) tags to public/<tag>/, master HEAD to
#   public/alpha/, and the latest active prerelease (an rc/a tag whose
#   base version has not yet shipped stable) to public/rc/<tag>/. Stale
#   public/rc/<other>/ subdirs are removed so the site never advertises
#   a release candidate whose base version has since shipped as a final
#   release.
# - Prerelease tag pipeline ($CI_COMMIT_TAG matches vX.Y.Z(rc|a)N): adds
#   a single subdirectory at public/rc/<tag>/ for the tagged docs.
#
# Both modes end by syncing the latest version_switcher.json into every
# public/**/_static/version_switcher.json so cached subdirs whose HTML
# predates the absolute-URL switch still pick up new entries.
#
# Required environment:
#   CI_DEFAULT_BRANCH  (default: master)
# Optional environment:
#   CI_COMMIT_TAG      (when set to vX.Y.Z(rc|a)N, switches to tag mode)

set -euo pipefail

ALPHA_REF="${CI_DEFAULT_BRANCH:-master}"
SWITCHER_JSON="docs/_static/version_switcher.json"
SCRIPT="docs/scripts/generate_version_switcher.py"

pip install -e '.[dev]'
pip install furo pydata-sphinx-theme

git fetch --tags --force origin "$ALPHA_REF"
python "$SCRIPT" --default-branch "$ALPHA_REF" --output "$SWITCHER_JSON"

build_docs_from_ref() {
    local ref="$1" output_dir="$2" docs_display_version="$3"
    local worktree_dir
    worktree_dir=$(mktemp -d)
    git worktree add --detach "$worktree_dir" "$ref"
    mkdir -p "$worktree_dir/docs/_static"
    cp "$SWITCHER_JSON" "$worktree_dir/$SWITCHER_JSON"
    DOCS_VERSION="$docs_display_version" sphinx-build \
        -D version="$docs_display_version" \
        -D release="$docs_display_version" \
        -b html "$worktree_dir/docs" "$output_dir"
    git worktree remove --force "$worktree_dir"
}

mkdir -p public

if [ -n "${CI_COMMIT_TAG:-}" ]; then
    # Prerelease tag pipeline: build only the tagged docs.
    build_docs_from_ref \
        "$CI_COMMIT_TAG" \
        "public/rc/$CI_COMMIT_TAG" \
        "$CI_COMMIT_TAG"
else
    # Branch pipeline: full rebuild of stable + alpha.
    HIGHEST_STABLE=$(python "$SCRIPT" --print-highest-stable)
    SELECTED_STABLE_TAGS=$(python "$SCRIPT" --print-selected-stable-tags)
    ALPHA_VERSION=$(python "$SCRIPT" --default-branch "$ALPHA_REF" --print-alpha-version)

    root_tmp_dir=$(mktemp -d)
    build_docs_from_ref "$HIGHEST_STABLE" "$root_tmp_dir" "$HIGHEST_STABLE"
    cp -a "$root_tmp_dir"/. public/
    rm -rf "$root_tmp_dir"

    for version_tag in $SELECTED_STABLE_TAGS; do
        if [ -f "public/$version_tag/index.html" ]; then
            echo "Skipping rebuild for existing version: $version_tag"
            continue
        fi
        build_docs_from_ref "$version_tag" "public/$version_tag" "$version_tag"
    done

    # Latest active prerelease (empty if every prerelease's base version
    # has already shipped as stable). Build it into public/rc/<tag>/, and
    # drop any stale public/rc/<other>/ subdirs left in the cache so the
    # site only ever advertises a currently-pending release candidate.
    LATEST_RC=$(python "$SCRIPT" --print-latest-rc-tag)
    if [ -d public/rc ]; then
        if [ -z "$LATEST_RC" ]; then
            rm -rf public/rc
        else
            find public/rc -mindepth 1 -maxdepth 1 -type d \
                ! -name "$LATEST_RC" -exec rm -rf {} +
        fi
    fi
    if [ -n "$LATEST_RC" ] && [ ! -f "public/rc/$LATEST_RC/index.html" ]; then
        build_docs_from_ref "$LATEST_RC" "public/rc/$LATEST_RC" "$LATEST_RC"
    fi

    build_docs_from_ref "origin/$ALPHA_REF" "public/alpha" "$ALPHA_VERSION"
fi

# Sync version_switcher.json into every existing _static directory.
# Use `\;` (one cp per match), not `+`: cp's multi-target form treats the
# last argument as a destination directory and would fail otherwise.
mkdir -p public/_static
cp "$SWITCHER_JSON" public/_static/version_switcher.json
find public -path '*/_static/version_switcher.json' \
    -exec cp "$SWITCHER_JSON" {} \;
