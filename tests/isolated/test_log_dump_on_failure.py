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
                [path_to_test_experiment("log_dump_error")],
                indirect=True,
            )
            def test_failure(launched_experiment):
                launched_experiment.test_experiment()
            """
        )
    )

    result = pytester.runpytest("-s")
    assert result.ret != 0
    result.stdout.fnmatch_lines(
        [
            "*PsyNet debug logs (tail)*",
            "*Traceback (most recent call last):*",
            "*NameError: name 'undefined_var' is not defined*",
        ]
    )
