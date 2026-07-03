from psynet.dev.slack_announcement import SECTION_TEXT_LIMIT, _split_mrkdwn


def test_split_mrkdwn_short_text_is_single_chunk():
    assert _split_mrkdwn("hello\nworld") == ["hello\nworld"]


def test_split_mrkdwn_splits_on_line_boundaries_below_limit():
    lines = [f"• entry {i} " + "x" * 200 for i in range(30)]
    chunks = _split_mrkdwn("\n".join(lines))
    assert len(chunks) > 1
    assert all(len(chunk) <= SECTION_TEXT_LIMIT for chunk in chunks)
    assert "\n".join(chunks).split("\n") == lines
