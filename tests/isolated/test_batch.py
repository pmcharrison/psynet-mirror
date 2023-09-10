import tempfile
from os.path import join

from psynet.media import make_batch_file, unpack_batch_file


def get_text_path(dir, text, suffix=""):
    return join(dir, text + suffix + ".txt")


def make_text_file(dir, text):
    with open(get_text_path(dir, text), "w") as f:
        f.write(text)


def test_batch():
    with tempfile.TemporaryDirectory() as tempdir:
        letters = ["a", "b", "c"]
        batch_path = join(tempdir, "letters.batch")
        input_files = [get_text_path(tempdir, letter) for letter in letters]
        reconstructed_output_files = [
            get_text_path(tempdir, letter, suffix="_reconstructed")
            for letter in letters
        ]
        for letter in letters:
            make_text_file(tempdir, letter)
        make_batch_file(input_files, batch_path)

        unpack_batch_file(batch_path, reconstructed_output_files)

        for i in range(len(letters)):
            with open(input_files[i], "r") as f:
                input_text = f.read()
            with open(reconstructed_output_files[i], "r") as f:
                reconstructed_text = f.read()
            assert input_text == reconstructed_text
