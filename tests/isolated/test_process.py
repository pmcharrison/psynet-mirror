import tempfile
import time

import pytest
from dallinger import db

import psynet.experiment  # noqa -- to ensure that all SQLAlchemy classes are registered
from psynet.process import LocalAsyncProcess
from psynet.pytest_psynet import path_to_test_experiment


def sleep_for_1s():
    time.sleep(1)


def failing_function():
    assert False, "This is an intentional error thrown for testing purposes."


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("static")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestProcesses:
    def test_process_that_fails(self):
        process = LocalAsyncProcess(failing_function)

        db.session.commit()
        time.sleep(0.5)
        db.session.commit()

        assert process.failed
        assert not process.finished
        assert not process.pending

    def test_async_process_participant(self, participant):
        assert len(participant.async_processes) == 0
        LocalAsyncProcess(sleep_for_1s, participant=participant)
        db.session.refresh(participant)
        assert len(participant.async_processes) == 1


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("static")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestProcesses2:
    def test_async_process_trial(self, trial, node, network, participant):
        # When a trial spawns an async process, this async process also is 'owned'
        # by the participant. The trial's node and network do not count as owners
        # of the process, however.
        db.session.commit()
        owners = [trial, participant]
        for o in owners:
            assert len(o.async_processes) == 0

        process = LocalAsyncProcess(sleep_for_1s, trial=trial)

        db.session.commit()

        for o in owners:
            assert len(o.async_processes) == 1

        time.sleep(1.5)

        db.session.commit()

        for o in owners:
            for p in o.async_processes:
                assert p.finished

        assert abs(process.time_taken - 1) < 0.5

    def test_invalid_function(self):
        def local_function():
            pass

        with pytest.raises(
            ValueError,
            match="You cannot serialize a lambda function or a function defined within another function.",
        ):
            LocalAsyncProcess(
                local_function,
                arguments={},
            )

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

            db.session.commit()

            with open(file.name, "r") as file_reader:
                assert file_reader.readline() != message

            time.sleep(1.5)

            db.session.commit()
            assert process.finished

            with open(file.name, "r") as file_reader:
                assert file_reader.readline() == message

            assert abs(process.time_taken - 0.5) < 0.1

    @staticmethod
    def sleep_then_write_to_file(duration, file, message):
        time.sleep(duration)

        with open(file, "w") as file_writer:
            file_writer.write(message)
