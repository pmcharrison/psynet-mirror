import tempfile
import time

import pytest

import psynet.experiment  # noqa -- to ensure that all SQLAlchemy classes are registered
from psynet.process import AsyncProcess


@pytest.mark.usefixtures("demo_mcmcp")
def test_invalid_function():
    def local_function():
        pass

    with pytest.raises(ValueError) as e:
        AsyncProcess(
            local_function,
            arguments={},
        )
        assert "The provided function could not be serialized" in str(e.value)


def sleep_then_write_to_file(duration, file, message):
    time.sleep(duration)

    with open(file, "w") as file_writer:
        file_writer.write(message)


@pytest.mark.usefixtures("demo_mcmcp")
def test_local_process():

    message = "Hello!"

    with tempfile.NamedTemporaryFile(delete=False) as file:
        AsyncProcess(
            sleep_then_write_to_file,
            dict(
                duration=0.125,
                file=file.name,
                message=message,
            ),
            local=True,
        )

        with open(file.name, "r") as file_reader:
            assert file_reader.readline() != message

        time.sleep(0.25)

        with open(file.name, "r") as file_reader:
            assert file_reader.readline() == message
