import numpy as np
from PIL import Image

RESOLUTION = 256


def fill_img(r, g, b):
    img = np.zeros([RESOLUTION, RESOLUTION, 3], dtype=np.uint8)
    for idx, color_component in enumerate([r, g, b]):
        img[:, :, idx].fill(color_component)
    return Image.fromarray(img)  # convert numpy array to image


def synth_stimulus(vector, output_path, chain_definition):
    """
    Synthesises a stimulus.

    Parameters
    ----------

    vector : list
        A vector of parameters as produced by the Gibbs sampler,
        for example:

        ::

            [0, 0, 112, 0, 152, 112, 0.5, 0.2]

    output_path : str
        The output path for the generated file.

    chain_definition
        The chain's definition object.
    """
    assert len(vector) == 3

    r, g, b = vector

    fill_img(r, g, b).save(f"{output_path}", format="PNG")
