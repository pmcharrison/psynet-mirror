from psynet.translation.translation import TranslationUnit


def test_get_codebook():
    # Test Jinja variables
    text = "Hello {{ NAME }}"
    codebook = TranslationUnit._get_codebook(text)
    assert codebook == [("{{ NAME }}", "■0■")]

    # Test simple variables
    text = "Hello {NAME}"
    codebook = TranslationUnit._get_codebook(text)
    assert codebook == [("{NAME}", "■0■")]

    # Test HTML tags
    text = "Hello <b>world</b>"
    codebook = TranslationUnit._get_codebook(text)
    assert codebook == [("<b>world</b>", "■0■")]

    # Test multiple variables
    text = "Hello {{ NAME }} {AGE} <b>world</b>"
    codebook = TranslationUnit._get_codebook(text)
    assert codebook == [
        ("{{ NAME }}", "■0■"),
        ("{AGE}", "■1■"),
        ("<b>world</b>", "■2■"),
    ]


def test_encode_decode():
    # Test encoding
    text = "Hello {{ NAME }} {AGE} <b>world</b>"
    codebook = TranslationUnit._get_codebook(text)
    encoded = TranslationUnit._encode(text, codebook)
    assert encoded == "Hello ■0■ ■1■ ■2■"

    # Test decoding
    decoded = TranslationUnit._decode(encoded, codebook)
    assert decoded == text

    # Test with empty text
    assert TranslationUnit._encode("", []) == ""
    assert TranslationUnit._decode("", []) == ""

    # Test with empty codebook
    assert TranslationUnit._encode("hello", []) == "hello"
    assert TranslationUnit._decode("hello", []) == "hello"
