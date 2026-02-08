import textwrap

pytest_plugins = ["pytester"]


def test_debug_logs_dumped_on_failure(pytester):
    pytester.makepyfile(
        test_failure=textwrap.dedent(
            """
            import pytest
            from psynet.pytest_psynet import path_to_test_experiment

            pytest_plugins = ["pytest_dallinger", "pytest_psynet"]


            @pytest.mark.parametrize(
                "experiment_directory",
                [path_to_test_experiment("timeline")],
                indirect=True,
            )
            def test_failure(debug_experiment):
                raise AssertionError("Intentional failure")
            """
        )
    )

    result = pytester.runpytest("-s")
    assert result.ret != 0
    result.stdout.fnmatch_lines(
        [
            "*PsyNet debug logs (tail)*",
            "*Experiment launch complete!*",
        ]
    )
