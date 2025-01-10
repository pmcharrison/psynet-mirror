from psynet.translation.translators import Translator


def test_get_codebook():
    # Test Jinja variables
    text = "Hello {{ NAME }}"
    codebook = Translator._get_codebook(text)
    assert codebook == [("{{ NAME }}", "■0■")]

    # Test simple variables
    text = "Hello {NAME}"
    codebook = Translator._get_codebook(text)
    assert codebook == [("{NAME}", "■0■")]

    # Test HTML tags
    text = "Hello <b>world</b>"
    codebook = Translator._get_codebook(text)
    assert codebook == [("<b>world</b>", "■0■")]

    # Test multiple variables
    text = "Hello {{ NAME }} {AGE} <b>world</b>"
    codebook = Translator._get_codebook(text)
    assert codebook == [
        ("{{ NAME }}", "■0■"),
        ("{AGE}", "■1■"),
        ("<b>world</b>", "■2■"),
    ]


def test_encode_decode():
    # Test encoding
    text = "Hello {{ NAME }} {AGE} <b>world</b>"
    codebook = Translator._get_codebook(text)
    encoded = Translator._encode(text, codebook)
    assert encoded == "Hello ■0■ ■1■ ■2■"

    # Test decoding
    decoded = Translator._decode(encoded, codebook)
    assert decoded == text

    # Test with empty text
    assert Translator._encode("", []) == ""
    assert Translator._decode("", []) == ""

    # Test with empty codebook
    assert Translator._encode("hello", []) == "hello"
    assert Translator._decode("hello", []) == "hello"
