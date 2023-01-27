import os
import uuid
from pathlib import Path

import jsonpickle

path = ".deploy/deployment_info.json"


def init(
    redeploying_from_archive: bool,
    mode: bool,
    is_local_deployment: bool,
    is_ssh_deployment: bool,
):
    secret = uuid.uuid4()
    write_all(locals())


def reset():
    write_all({})


def write_all(content: dict):
    encoded = jsonpickle.encode(content, indent=4)

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


def read_all():
    with open(path, "r") as file:
        txt = file.read()
    content = jsonpickle.decode(txt)
    assert isinstance(content, dict)
    return content


def read(key):
    content = read_all()
    return content[key]


def delete():
    os.remove(path)
