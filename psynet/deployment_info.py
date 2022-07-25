import os
from pathlib import Path

import jsonpickle

path = "deploy/deployment_info.json"


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
    try:
        with open(path, "r") as file:
            txt = file.read()
        content = jsonpickle.decode(txt)
    except FileNotFoundError:
        content = {}
    assert isinstance(content, dict)
    return content


def read(key):
    content = read_all()
    return content[key]
