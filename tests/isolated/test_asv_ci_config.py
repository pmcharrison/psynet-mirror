import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_asv_uninstall_drops_dallinger_between_commits():
    """Shared ASV envs must not keep the previous commit's Dallinger.

    ``asv continuous`` reuses one virtualenv. Pip will keep an already-installed
    Dallinger when the next commit's requirement is still satisfied, which is
    how the deploy.toml cutover left old PsyNet calling ``apply_to`` with
    ``shutil.copyfile`` against plan-backed Dallinger 12.4.
    """
    conf = json.loads((ROOT / "asv.conf.json").read_text(encoding="utf-8"))
    uninstall = " ".join(conf["uninstall_command"])
    assert "{project}" in uninstall
    assert "dallinger" in uninstall


def test_asv_benchmarks_job_uploads_snapshot_outside_the_results_worktree():
    ci = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
    asv_job = ci.split("asv_benchmarks:")[1].split("asv_regression:")[0]
    assert ".asv/ci-artifacts/" in asv_job
    assert "optional: true" in asv_job
    assert ".asv/results/" not in asv_job.split("artifacts:")[1]


def test_snapshot_results_for_ci_excludes_worktree_git_metadata(tmp_path):
    results = tmp_path / "results"
    machine = results / "gitlab-ci"
    machine.mkdir(parents=True)
    (machine / "example.json").write_text('{"commit_hash": "abc"}\n', encoding="utf-8")
    (results / ".git").write_text("gitdir: /tmp/worktrees/benchmark-results\n")
    artifacts = tmp_path / "ci-artifacts"

    script = f"""
    set -euo pipefail
    RESULTS_DIR={results.as_posix()!r}
    REPO_ROOT={tmp_path.as_posix()!r}
    ARTIFACT_RESULTS_DIR={artifacts.as_posix()!r}
    source {(ROOT / "ci/asv-worktree-lib.sh").as_posix()!r}
    snapshot_results_for_ci
    """
    subprocess.run(["bash", "-c", script], check=True)

    assert (artifacts / "gitlab-ci" / "example.json").read_text(
        encoding="utf-8"
    ) == '{"commit_hash": "abc"}\n'
    assert not (artifacts / ".git").exists()


def test_snapshot_results_for_ci_skips_empty_worktree(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    (results / ".git").write_text("gitdir: /tmp/worktrees/benchmark-results\n")
    artifacts = tmp_path / "ci-artifacts"

    script = f"""
    set -euo pipefail
    RESULTS_DIR={results.as_posix()!r}
    REPO_ROOT={tmp_path.as_posix()!r}
    ARTIFACT_RESULTS_DIR={artifacts.as_posix()!r}
    source {(ROOT / "ci/asv-worktree-lib.sh").as_posix()!r}
    snapshot_results_for_ci
    """
    subprocess.run(["bash", "-c", script], check=True)
    assert not artifacts.exists()
