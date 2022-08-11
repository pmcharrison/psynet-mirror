import tempfile
import time

import pytest
from dallinger import db

import psynet.experiment  # noqa -- to ensure that all SQLAlchemy classes are registered
from psynet.process import LocalAsyncProcess


def sleep_for_1s():
    time.sleep(1)


def failing_function():
    assert False, "This is an intentional error thrown for testing purposes."


@pytest.mark.parametrize("experiment_directory", ["../demos/static"], indirect=True)
@pytest.mark.usefixtures("launched_experiment")
class TestProcesses:
    def test_process_that_fails(self):
        process = LocalAsyncProcess(failing_function)
        time.sleep(0.5)
        db.session.commit()

        assert process.failed
        assert not process.finished
        assert not process.pending

    def test_awaiting_async_process_participant(self, participant):
        assert not participant.awaiting_async_process
        LocalAsyncProcess(sleep_for_1s, participant=participant)
        db.session.refresh(participant)
        assert participant.awaiting_async_process

    def test_awaiting_async_process_trial(self, trial, node, network, participant):
        owners = [trial, node, network, participant]
        for o in owners:
            assert not o.awaiting_async_process

        process = LocalAsyncProcess(sleep_for_1s, trial=trial)

        for o in owners:
            db.session.refresh(o)
            assert o.awaiting_async_process

        time.sleep(1.5)

        db.session.refresh(process)

        for o in owners:
            db.session.refresh(o)
            assert not o.awaiting_async_process

        assert abs(process.time_taken - 1) < 0.1

    def test_invalid_function(self):
        def local_function():
            pass

        with pytest.raises(ValueError) as e:
            LocalAsyncProcess(
                local_function,
                arguments={},
            )
        assert "The provided function could not be serialized" in str(e.value)

        class A:
            def instance_method(self):
                pass

            @classmethod
            def class_method(cls):
                pass

        a = A()

        with pytest.raises(ValueError) as e:
            LocalAsyncProcess(
                a.instance_method,
                arguments={},
            )
            assert "You cannot pass an instance method to an AsyncProcess." in str(
                e.value
            )

    def test_local_process(self):
        message = "Hello!"

        with tempfile.NamedTemporaryFile(delete=False) as file:
            process = LocalAsyncProcess(
                self.sleep_then_write_to_file,
                dict(
                    duration=0.5,
                    file=file.name,
                    message=message,
                ),
            )

            with open(file.name, "r") as file_reader:
                assert file_reader.readline() != message

            time.sleep(0.75)

            db.session.refresh(process)
            assert process.finished

            with open(file.name, "r") as file_reader:
                assert file_reader.readline() == message

            assert abs(process.time_taken - 0.5) < 0.1

    @staticmethod
    def sleep_then_write_to_file(duration, file, message):
        time.sleep(duration)

        with open(file, "w") as file_writer:
            file_writer.write(message)
