# Note: this implementation assumes ffmpeg is installed

import subprocess
import tempfile

import numpy as np
from PIL import Image

RESOLUTION = 256
STIM_LEN_S = 3


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
    assert len(vector) == 8

    r1, g1, b1, r2, g2, b2, dur1, dur2 = vector
    durations = [dur1, dur2]
    assert sum(durations) < STIM_LEN_S

    with tempfile.TemporaryDirectory() as out_dir:
        for i, (r, g, b) in enumerate([[r1, g1, b1], [r2, g2, b2]]):
            # Create image
            fill_img(r, g, b).save(f"{out_dir}/img{i + 1}.jpg")

            # Convert to still
            subprocess.call(
                f"ffmpeg -y -loop 1 -i {out_dir}/img{i + 1}.jpg -c:v libx264 -t {durations[i]} -pix_fmt yuv420p -vf scale=320:240 {out_dir}/out{i + 1}.mp4",
                shell=True,
            )

        subprocess.call(
            f"cd {out_dir};for f in *.mp4; do echo \"file '$f'\" >> videos.txt; done",
            shell=True,
        )
        subprocess.call(
            f"cd {out_dir};ffmpeg -f concat -i {out_dir}/videos.txt -c copy {out_dir}/comb.mp4",
            shell=True,
        )

        repetitions = int(STIM_LEN_S // (dur1 + dur2))
        subprocess.call(
            f"ffmpeg -stream_loop {repetitions} -i {out_dir}/comb.mp4 -c copy {output_path}",
            shell=True,
        )
