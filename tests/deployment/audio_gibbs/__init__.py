try:
    import pytest
except ImportError:
    # Production images do not install pytest; skip assert rewriting there.
    pass
else:
    # Rewrite `assert` calls in `experiment.py` so pytest failures are more useful.
    pytest.register_assert_rewrite("dallinger_experiment.experiment")
