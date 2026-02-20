import psynet.experiment
from psynet.page import InfoPage
from psynet.timeline import CodeBlock, Timeline


def run_catr_smoke_test():
    """
    Execute a small catR computation via rpy2.

    Returns
    -------
    float
        Ability estimate returned by catR's ``thetaEst``.
    """
    try:
        from rpy2 import robjects
    except ImportError as error:
        raise RuntimeError(
            "Could not import rpy2. Add rpy2 to requirements.txt."
        ) from error

    try:
        theta = robjects.r(
            """
            suppressMessages(library(catR))

            item_bank <- matrix(c(
                1.2, -1.0, 0.0, 1.0,
                1.0,  0.0, 0.0, 1.0,
                1.3,  0.8, 0.0, 1.0
            ), ncol = 4, byrow = TRUE)

            responses <- c(1, 0, 1)
            theta <- thetaEst(it = item_bank, x = responses, method = "ML")
            as.numeric(theta)
            """
        )
    except Exception as error:
        raise RuntimeError(
            "Failed to execute catR. Ensure R and catR are installed "
            "via prepare_docker_image.sh."
        ) from error

    return float(theta[0])


def verify_catr_in_timeline(participant):
    theta = run_catr_smoke_test()
    if not isinstance(theta, float):
        raise RuntimeError("catR smoke test did not return a float value.")
    participant.var.set("catr_theta", theta)


class Exp(psynet.experiment.Experiment):
    label = "Adaptive testing with catR"

    timeline = Timeline(
        CodeBlock(verify_catr_in_timeline),
        InfoPage(
            "This demo shows how to call catR (R) from PsyNet via rpy2.",
            time_estimate=5,
        ),
    )
