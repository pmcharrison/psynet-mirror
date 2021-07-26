"""
This is an example script to show how to create an audio batch from
audio files (wav) stored in a static folder.

First, specify your input and output directories, for example:
input_dir = "static/audio/rhythms"
output_dir = "static/audio/batch.rhythms"

Second, run the two functions below in the python console from the working dir of the project.
Finally, run make_batch_from_paths(input_dir, output_dir) in the pythion console.
"""


def get_filepaths(directory, suffix=".wav"):
    import os

    paths = []
    for root, directories, files in os.walk(directory):  # Walk the tree.
        for filename in files:
            if filename.endswith(suffix):
                path = os.path.join(root, filename)
                paths.append(path)  # Add it to the list.
    import re

    paths.sort(
        key=lambda var: [
            int(x) if x.isdigit() else x for x in re.findall(r"[^0-9]|[0-9]+", var)
        ]
    )
    return paths


def make_batch_from_paths(input_dir, output_dir):
    from psynet.media import make_batch_file

    file_paths = get_filepaths(input_dir)
    for path in file_paths:
        make_batch_file(file_paths, output_dir)
