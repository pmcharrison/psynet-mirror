import psynet.experiment
from psynet.page import InfoPage
from psynet.timeline import CodeBlock, Timeline


def run_catr_smoke_test():
    """
    Execute a minimal catR call via rpy2.

    Returns
    -------
    str
        Installed catR version string.
    """
    try:
        from rpy2 import robjects
    except ImportError as error:
        raise RuntimeError(
            "Could not import rpy2. Add rpy2 to requirements.txt."
        ) from error

    try:
        catr_version = robjects.r(
            """
            suppressMessages(library(catR))
            as.character(packageVersion("catR"))
            """
        )
    except Exception as error:
        raise RuntimeError(
            "Failed to execute catR. Ensure R and catR are installed "
            "via prepare_docker_image.sh."
        ) from error

    return str(catr_version[0])


def verify_catr_in_timeline():
    catr_version = run_catr_smoke_test()
    if not catr_version:
        raise RuntimeError("catR smoke test returned an empty version string.")


class Exp(psynet.experiment.Experiment):
    label = "Adaptive testing with catR"

    timeline = Timeline(
        CodeBlock(verify_catr_in_timeline),
        InfoPage(
            "This demo shows how to call catR (R) from PsyNet via rpy2.",
            time_estimate=5,
        ),
    )

    def test_experiment(self):
        verify_catr_in_timeline()
