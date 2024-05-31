def bold(text: str):
    """
    Use this within e.g. ``logger.info`` to format text in bold.
    """
    bold_start, bold_end = "\033[1m", "\033[0m"
    return bold_start + text + bold_end


def red(text: str):
    """
    Use this within e.g. ``logger.info`` to format text in red.
    """
    red_start, red_end = "\033[91m", "\033[0m"
    return red_start + text + red_end
