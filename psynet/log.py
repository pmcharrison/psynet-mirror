def bold(text: str):
    """
    Use this within e.g. ``logger.info`` to format text in bold.
    """
    bold_start, bold_end = "\033[1m", "\033[0m"
    return bold_start + text + bold_end
