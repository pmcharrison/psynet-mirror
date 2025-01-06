import pytest

from psynet.translation.translation import translate_experiment


@pytest.mark.usefixtures("in_experiment_directory")
@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("mcmcp")], indirect=True
)
def test_translate_experiment(in_ex):

