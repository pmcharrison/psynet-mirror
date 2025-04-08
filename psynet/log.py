def bold(text: str):
    """
    Use this within e.g. ``logger.info`` to format text in bold.
    """
    bold_start, bold_end = "\033[1m", "\033[0m"
    return f"{bold_start}{text}{bold_end}"


def red(text: str):
    """
    Use this within e.g. ``logger.info`` to format text in red.
    """
    red_start, red_end = "\033[91m", "\033[0m"
    return f"{red_start}{text}{red_end}"


def success(text):
    green_start, green_end = "\033[92m", "\033[0m"
    return f"{green_start}{text}{green_end}"


def warning(text):
    yellow_start, yellow_end = "\033[93m", "\033[0m"
    return f"{yellow_start}{text}{yellow_end}"


def error(text):
    return red(text)
