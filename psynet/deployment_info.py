import os
import subprocess
import uuid
from pathlib import Path

import jsonpickle
from tenacity import retry, stop_after_attempt, wait_fixed

from .utils import find_git_repo

path = ".deploy/deployment_info.json"


def _git_output(*args):
    """Run Git and return stripped output, or ``None`` when unavailable."""
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _get_git_provenance():
    """Return the current commit SHA and working-tree dirty state."""
    commit_sha = _git_output("rev-parse", "HEAD")
    if commit_sha is None:
        return None, None
    status = _git_output("status", "--porcelain", "--untracked-files=normal")
    return commit_sha, None if status is None else bool(status)


def init(
    redeploying_from_archive: bool,
    mode: str,
    is_local_deployment: bool,
    is_ssh_deployment: bool,
    server: str,
    app: str,
    folder_name: str = os.path.basename(os.getcwd()),
):
    secret = uuid.uuid4()
    origin = find_git_repo()
    git_commit_sha, git_dirty = _get_git_provenance()
    write_all(locals())


def is_available():
    return os.path.exists(path)


def reset():
    write_all({})


def write_all(content: dict):
    encoded = jsonpickle.encode(content, indent=4, keys=True)

    def f():
        with open(path, "w") as file:
            file.write(encoded)

    try:
        f()
    except FileNotFoundError:
        Path(os.path.dirname(path)).mkdir(parents=True, exist_ok=True)
        f()


def write(**kwargs):
    content = read_all()
    content.update(**kwargs)
    write_all(content)


@retry(stop=stop_after_attempt(5), wait=wait_fixed(1), reraise=True)
def read_all():
    with open(path, "r") as file:
        txt = file.read()
    content = jsonpickle.decode(txt, keys=True)
    assert isinstance(content, dict)
    return content


def read(key):
    content = read_all()
    return content[key]


def delete():
    os.remove(path)
