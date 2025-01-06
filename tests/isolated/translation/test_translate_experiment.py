import pytest

from psynet.pytest_psynet import path_to_test_experiment
from psynet.translation.translation import check_languages, translate_experiment


def test_check_languages():
    assert check_languages(["fr", "de"])

    with pytest.raises(ValueError, match="Unknown language: asdas"):
        check_languages(["asdas"])


@pytest.mark.usefixtures("in_experiment_directory")
@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("translation")], indirect=True
)
def test_translate_experiment():
    translate_experiment(["fr"])
