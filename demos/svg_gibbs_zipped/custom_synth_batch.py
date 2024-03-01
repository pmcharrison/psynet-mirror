import os

from psynet.media import make_batch_file


def fill_svg(vector, width=250, height=250):
    r, g, b = vector
    svg = (
        f'<?xml version="1.0" encoding="ASCII" standalone="yes"?>'
        f'<svg xmlns="http://www.w3.org/2000/svg" id = "inlineSVG" width="{width}" height="{height}">'
        f'<rect x="0" y="0" width="{width / 3}" height="{height / 3}" style="fill:rgb({r},{g},{b});" ></rect>'
        f'<rect x="{width / 2}" y="0" width="{width / 3}" height="{height / 3}" style="fill:rgb({r},{g},{b});" ></rect>'
        f'<rect x="0" y="{width / 2}" width="{width / 3}" height="{height / 3}" style="fill:rgb({r},{g},{b});" ></rect>'
        f'<rect x="{width / 2}" y="{width / 2}" width="{width / 3}" height="{height / 3}" style="fill:rgb({r},{g},{b});" ></rect>'
        f"</rect>"
        f"Sorry, your browser does not support inline SVG."
        f"</svg>"
    )
    return svg


def synth_batch(vector, output_path, chain_definition):
    """
    Creates a set of stimuli based on given parameters.

    Parameters
    ----------

    vector : list
        A list of vectors of parameters as produced by the Gibbs sampler,
        for example:

        ::

            [ [0, 0, 10], [0, 0, 50], [0, 0, 90] ]

    output_path : str
        The output path for the generated file.

    chain_definition
        The chain's definition object.
    """
    n_stimuli = len(vector)

    temp_dir = os.path.dirname(output_path)
    individual_stimuli_dir = os.path.join(temp_dir, "individual_stimuli")
    if os.path.isdir(individual_stimuli_dir):
        pass
    else:
        os.mkdir(individual_stimuli_dir)

    ids = [f"slider_stimulus_{_i}" for _i, _ in enumerate(range(n_stimuli))]
    files = [f"{_id}{'.svg'}" for _id in ids]
    paths = [os.path.join(individual_stimuli_dir, _file) for _file in files]

    for index in range(n_stimuli):
        updated_vector = vector[index]
        svg = fill_svg(updated_vector)

        with open(f"{paths[index]}", "w") as file:
            file.write(f"{svg}")
            file.flush()

    make_batch_file(paths, output_path)
