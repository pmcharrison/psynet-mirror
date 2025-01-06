from unittest import mock
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from psynet.translation.command_line import generate


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_translate_exp():
    with patch("psynet.translation.command_line.translate_experiment") as mock:
        yield mock


@pytest.fixture
def mock_translate_pkg():
    with patch("psynet.translation.command_line.translate_package") as mock:
        yield mock


def test_generate_experiment_only(runner, mock_translate_exp, mock_translate_pkg):
    result = runner.invoke(generate, ["--experiment", "--languages", "fr"])
    assert result.exit_code == 0
    assert "Translating experiment to fr..." in result.output
    assert "Translating psynet package to fr..." not in result.output
    mock_translate_exp.assert_called_once_with("fr")
    mock_translate_pkg.assert_not_called()


def test_generate_package_only(runner, mock_translate_exp, mock_translate_pkg):
    result = runner.invoke(generate, ["--packages", "psynet", "--languages", "fr"])
    assert result.exit_code == 0
    assert "Translating psynet package to fr..." in result.output
    assert "Translating experiment to fr..." not in result.output
    mock_translate_pkg.assert_called_once_with("psynet", "fr")
    mock_translate_exp.assert_not_called()


def test_generate_experiment_and_package(
    runner, mock_translate_exp, mock_translate_pkg
):
    result = runner.invoke(
        generate, ["--experiment", "--packages", "psynet", "--languages", "fr"]
    )
    assert result.exit_code == 0
    assert "Translating experiment to fr..." in result.output
    assert "Translating psynet package to fr..." in result.output
    mock_translate_exp.assert_called_once_with("fr")
    mock_translate_pkg.assert_called_once_with("psynet", "fr")


def test_generate_multiple_languages(runner, mock_translate_exp, mock_translate_pkg):
    result = runner.invoke(generate, ["--experiment", "--languages", "fr de"])
    assert result.exit_code == 0
    assert "Translating experiment to fr..." in result.output
    assert "Translating experiment to de..." in result.output
    assert mock_translate_exp.call_count == 2
    assert mock_translate_exp.call_args_list == [mock.call("fr"), mock.call("de")]
    mock_translate_pkg.assert_not_called()


def test_generate_comma_separated_languages(
    runner, mock_translate_exp, mock_translate_pkg
):
    result = runner.invoke(generate, ["--experiment", "--languages", "fr,de"])
    assert result.exit_code == 0
    assert "Translating experiment to fr..." in result.output
    assert "Translating experiment to de..." in result.output
    mock_translate_exp.assert_has_calls([mock.call("fr"), mock.call("de")])
    mock_translate_pkg.assert_not_called()
