import os
import tempfile

import pytest
from dallinger import db

import psynet.experiment  # noqa -- Need to import this for SQLAlchemy registrations to work properly
from psynet.asset import CachedFunctionAsset, ExperimentAsset, LocalStorage
from psynet.pytest_psynet import path_to_demo


class MultiplyAsset(ExperimentAsset):
    def after_deposit(self):
        with open(self.input_path, "r") as f:
            self.var.x = int(f.read())
            self.var.y = self.var.x * 3


@pytest.fixture
def debug_storage(in_experiment_directory):
    with tempfile.TemporaryDirectory() as tempdir:
        yield LocalStorage(tempdir)


@pytest.fixture
def folder_asset(debug_storage):
    with tempfile.TemporaryDirectory() as tempdir:
        path_1 = os.path.join(tempdir, "file_1.txt")
        path_2 = os.path.join(tempdir, "file_2.txt")

        subdir = os.path.join(tempdir, "subdir")
        path_3 = os.path.join(subdir, "file_3.txt")

        with open(path_1, "w") as f:
            f.write("File 1")

        with open(path_2, "w") as f:
            f.write("File 2")

        os.mkdir(subdir)

        with open(path_3, "w") as f:
            f.write("File 3")

        asset = ExperimentAsset(
            "test_folder_asset",
            tempdir,
            is_folder=True,
        )
        asset.deposit(debug_storage)

        yield asset


@pytest.fixture
def folder_asset_clone(debug_storage):
    with tempfile.TemporaryDirectory() as tempdir:
        path_1 = os.path.join(tempdir, "file_1.txt")
        path_2 = os.path.join(tempdir, "file_2.txt")

        subdir = os.path.join(tempdir, "subdir")
        path_3 = os.path.join(subdir, "file_3.txt")

        with open(path_1, "w") as f:
            f.write("File 1")

        with open(path_2, "w") as f:
            f.write("File 2")

        os.mkdir(subdir)

        with open(path_3, "w") as f:
            f.write("File 3")

        asset = ExperimentAsset(
            "test_folder_asset_2",
            tempdir,
            is_folder=True,
        )
        asset.deposit(debug_storage)

        yield asset


@pytest.mark.usefixtures("in_experiment_directory")
@pytest.mark.parametrize(
    "experiment_directory", [path_to_demo("static")], indirect=True
)
class AssetTests:
    def test_lambda_function(self):
        with pytest.raises(ValueError) as e:
            CachedFunctionAsset(function=lambda path, x: x + 1)
        assert (
            str(e.value)
            == "'function' cannot be a lambda function, please provide a named function instead"
        )

    def test_key(self):
        def f(path):
            pass

        asset_1 = CachedFunctionAsset(function=f)
        asset_2 = CachedFunctionAsset(function=f, key="asset_2")

        assert not asset_1.has_key
        assert asset_2.has_key

    def test_md5_folder(self, folder_asset, folder_asset_clone):
        assert folder_asset.is_folder
        assert folder_asset.get_md5_contents() == folder_asset_clone.get_md5_contents()

    def test_infer_file(self):
        with tempfile.TemporaryDirectory() as tempdir:
            file_path = tempdir + "/file.txt"
            with open(file_path, "w") as file:
                file.write("Hello!")

                asset = ExperimentAsset(
                    local_key="test",
                    input_path=file_path,
                )
                assert isinstance(asset.is_folder, bool) and not asset.is_folder

                asset_2 = ExperimentAsset(
                    local_key="test_2",
                    input_path=tempdir,
                )
                assert isinstance(asset_2.is_folder, bool) and asset_2.is_folder

    def test_export_subfile(
        self, folder_asset, debug_storage, deployment_info, db_session
    ):
        folder_asset.deposit(storage=debug_storage)

        # Exporting the whole folder at once
        with tempfile.TemporaryDirectory() as tempdir:
            folder_asset.export(tempdir)

            with open(tempdir + "/file_1.txt", "r") as file:
                assert file.read() == "File 1"

            with open(tempdir + "/file_2.txt", "r") as file:
                assert file.read() == "File 2"

        # Exporting single files
        with tempfile.TemporaryDirectory() as tempdir:
            temp_path = tempdir + "/file_2.txt"
            folder_asset.export_subfile("file_2.txt", temp_path)

            assert not os.path.exists(tempdir + "/file_1.txt")
            assert os.path.exists(tempdir + "/file_2.txt")

            with open(temp_path, "r") as file:
                assert file.read() == "File 2"

        # Export subdirectory
        with tempfile.TemporaryDirectory() as tempdir:
            folder_asset.export_subfolder("subdir", tempdir)

            with open(os.path.join(tempdir, "file_3.txt"), "r") as file:
                assert file.read() == "File 3"

    @pytest.mark.parametrize("async_", [True, False])
    def test_after_deposit(async_, db_session, debug_storage, deployment_info):
        from dallinger import db

        from psynet.utils import wait_until

        try:
            file = tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt")
            file.write("42")
            file.flush()

            asset = MultiplyAsset(
                "test",
                file.name,
            )

            asset.deposit(debug_storage, async_=async_)

            def deposit_complete():
                db.session.refresh(asset)
                return asset.deposited

            wait_until(deposit_complete, max_wait=5, poll_interval=0.2)

            assert asset.var.x == 42
            assert asset.var.y == 126

        finally:
            os.remove(file.name)


@pytest.mark.parametrize(
    "experiment_directory", [path_to_demo("static")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
def test_access_assets(
    node,
    trial_class,
    debug_storage,
    experiment_object,
    participant,
    launched_experiment,
):
    trials = [
        trial_class(
            experiment=experiment_object,
            node=node,
            participant=participant,
            propagate_failure=False,
            is_repeat_trial=False,
        )
        for _ in range(2)
    ]
    for t in trials:
        db.session.add(t)
    db.session.commit()

    with tempfile.NamedTemporaryFile("w", suffix=".txt") as f:
        f.write("Hello!")
        f.flush()

        node_asset = ExperimentAsset(
            local_key="node_asset",
            input_path=f.name,
            parent=node,
        )
        node_asset.deposit(debug_storage)

        for t in trials:
            trial_asset = ExperimentAsset(
                local_key="trial_asset",
                input_path=f.name,
                parent=t,
            )
            trial_asset.deposit(debug_storage)

    db.session.commit()

    assert len(node.assets) == 1
    assert isinstance(node.assets["node_asset"], ExperimentAsset)
    assert node.assets["node_asset"].export_path.endswith(".txt")
    assert not node.assets["node_asset"].key_within_experiment.endswith(".txt")

    for t in trials:
        assert len(t.assets) == 1
        assert isinstance(t.assets["trial_asset"], ExperimentAsset)
        assert t.assets["trial_asset"].export_path.endswith(".txt")
