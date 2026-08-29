"""Fail launch if this directory's experiment.py was baked into the wrong image.

Dallinger ``<= 12.3.0`` tags images from ``requirements.txt`` and
``prepare_docker_image.sh`` only. Two recruiter variants can then reuse
one image. Each ``experiment.py*`` calls this on launch with the recruiter
that file is written for.
"""

_ALLOWED = {
    "hotair": frozenset({"hotair"}),
    "prolific": frozenset({"prolific", "devprolific"}),
    "lucid": frozenset({"lucid-recruiter", "lucid"}),
}


def assert_expected_recruiter(expected):
    """Raise if config ``recruiter`` is not one of the names for ``expected``."""
    from dallinger.config import get_config

    recruiter = get_config().get("recruiter")
    allowed = _ALLOWED[expected]
    if recruiter not in allowed:
        raise RuntimeError(
            f"experiment.py is the {expected} variant but config "
            f"recruiter={recruiter!r}. A shared Docker image was probably "
            f"reused. Rebuild from this experiment directory after copying "
            f"the matching prepare_docker_image.sh."
        )
