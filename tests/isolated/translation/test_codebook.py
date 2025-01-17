from psynet.translation.translators import Translator


def test_get_codebook_jinja_variables():
    text = "Hello {{ NAME }}"
    codebook = Translator._get_codebook(text)
    assert codebook == [("{{ NAME }}", "■0■")]


def test_get_codebook_simple_variables():
    text = "Hello {NAME}"
    codebook = Translator._get_codebook(text)
    assert codebook == [("{NAME}", "■0■")]


def test_get_codebook_html_tags():
    text = "Hello <b>world</b>"
    codebook = Translator._get_codebook(text)
    assert codebook == [("<b>", "■0■"), ("</b>", "■1■")]


def test_get_codebook_multiple_variables():
    text = "Hello {{ NAME }} {AGE} <b>world</b>"
    codebook = Translator._get_codebook(text)
    assert codebook == [
        ("{{ NAME }}", "■0■"),
        ("{AGE}", "■1■"),
        ("<b>", "■2■"),
        ("</b>", "■3■"),
    ]


def test_get_codebook_html_with_attributes():
    text = '<div class="alert alert-primary" role="alert">Hello</div>'
    codebook = Translator._get_codebook(text)
    assert codebook == [
        ('<div class="alert alert-primary" role="alert">', "■0■"),
        ("</div>", "■1■"),
    ]


def test_encode_decode():
    # Test encoding
    text = "Hello {{ NAME }} {AGE} <b>world</b>"
    codebook = Translator._get_codebook(text)
    encoded = Translator._encode(text, codebook)
    assert encoded == "Hello ■0■ ■1■ ■2■world■3■"

    # Test decoding
    decoded = Translator._decode(encoded, codebook)
    assert decoded == text

    # Test with empty text
    assert Translator._encode("", []) == ""
    assert Translator._decode("", []) == ""

    # Test with empty codebook
    assert Translator._encode("hello", []) == "hello"
    assert Translator._decode("hello", []) == "hello"
