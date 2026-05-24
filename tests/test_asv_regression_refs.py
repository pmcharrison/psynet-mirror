import os
import shlex
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ASV_REFS_SCRIPT = REPO_ROOT / "ci" / "asv-regression-refs.sh"


def run(command, cwd, env=None):
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def git(cwd, *args):
    return run(["git", *args], cwd)


def commit_file(cwd, path, content, message):
    target = cwd / path
    target.write_text(content)
    git(cwd, "add", str(path))
    git(cwd, "commit", "-m", message)
    return git(cwd, "rev-parse", "HEAD")


def make_mr_repo(tmp_path):
    origin = tmp_path / "origin.git"
    source = tmp_path / "source"
    runner = tmp_path / "runner"

    run(["git", "init", "--bare", str(origin)], tmp_path)
    run(["git", "clone", str(origin), str(source)], tmp_path)
    git(source, "config", "user.name", "Test User")
    git(source, "config", "user.email", "test@example.com")

    commit_file(source, Path("README.md"), "base\n", "base")
    git(source, "push", "-u", "origin", "master")

    git(source, "checkout", "-b", "feature")
    feature_sha = commit_file(
        source,
        Path("feature.txt"),
        "feature\n",
        "feature change",
    )
    git(source, "push", "-u", "origin", "feature")

    git(source, "checkout", "master")
    master_sha = commit_file(
        source,
        Path("target.txt"),
        "target\n",
        "target change",
    )
    git(source, "push", "origin", "master")

    run(["git", "clone", str(origin), str(runner)], tmp_path)
    git(runner, "checkout", "feature")

    return source, runner, master_sha, feature_sha


def source_asv_refs(repo, env):
    merged_env = {
        **os.environ,
        **env,
    }
    command = (
        f". {shlex.quote(str(ASV_REFS_SCRIPT))} >/dev/null && "
        "printf '__ASV_BASE=%s\\n__ASV_HEAD=%s\\n' "
        '"$ASV_BASE" "$ASV_HEAD"'
    )
    output = run(["/bin/sh", "-c", command], repo, env=merged_env)
    return {
        key.removeprefix("__ASV_"): value
        for key, value in (line.split("=", 1) for line in output.splitlines())
    }


def test_detached_mr_pipeline_synthesizes_merge_commit(tmp_path):
    _, runner, master_sha, feature_sha = make_mr_repo(tmp_path)

    refs = source_asv_refs(
        runner,
        {
            "CI_MERGE_REQUEST_TARGET_BRANCH_NAME": "master",
            "CI_MERGE_REQUEST_EVENT_TYPE": "detached",
            "CI_COMMIT_SHA": feature_sha,
        },
    )

    parents = git(runner, "rev-list", "--parents", "-n", "1", refs["HEAD"]).split()

    assert refs["BASE"] == master_sha
    assert parents == [refs["HEAD"], master_sha, feature_sha]


def test_merged_result_pipeline_uses_gitlab_merge_commit(tmp_path):
    source, runner, master_sha, feature_sha = make_mr_repo(tmp_path)
    git(source, "checkout", "-B", "merge-result", master_sha)
    git(source, "merge", "--no-ff", "--no-edit", feature_sha)
    merge_sha = git(source, "rev-parse", "HEAD")
    git(source, "push", "-u", "origin", "merge-result")

    git(runner, "fetch", "origin", "merge-result")
    git(runner, "checkout", "--detach", "FETCH_HEAD")

    refs = source_asv_refs(
        runner,
        {
            "CI_MERGE_REQUEST_TARGET_BRANCH_NAME": "master",
            "CI_MERGE_REQUEST_TARGET_BRANCH_SHA": master_sha,
            "CI_MERGE_REQUEST_EVENT_TYPE": "merged_result",
            "CI_COMMIT_SHA": merge_sha,
        },
    )

    assert refs == {"BASE": master_sha, "HEAD": merge_sha}
    assert git(runner, "rev-parse", "HEAD") == merge_sha
