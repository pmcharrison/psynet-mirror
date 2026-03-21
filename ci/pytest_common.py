WARNING_FILTER = (
    "ignore:color, on_color and attrs are not supported when output stream is "
    "not a TTY:UserWarning:yaspin.core"
)


def build_pytest_common_args(timeout_seconds, log_cli=False, quiet=True):
    args = [
        "-Werror",
        "-W",
        WARNING_FILTER,
        "-o",
        f"log_cli={'True' if log_cli else 'False'}",
        "--chrome",
        f"--timeout={timeout_seconds}",
    ]
    if quiet:
        args.append("-q")
    return args
