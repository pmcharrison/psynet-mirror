def fill_svg(r, g, b, width=250, height=250):
    svg = (
        f'<?xml version="1.0" encoding="ASCII" standalone="yes"?>'
        f'<svg xmlns="http://www.w3.org/2000/svg" id = "inlineSVG" width="{width}" height="{height}">'
        f'<rect width="{width}" height="{height}" style="fill:rgb({r},{g},{b});" >'
        f'<animate id = "animation" attributeName="fill" begin="0s" calcMode="linear" dur="5s" '
        f'repeatCount="indefinite" values="rgb({r},{g},{b});white;rgb({r},{g},{b})"></animate>'
        f"</rect>"
        f"Sorry, your browser does not support inline SVG."
        f"</svg>"
    )
    return svg


def synth_stimulus(vector, output_path, chain_definition):
    """
    Synthesises a stimulus.

    Parameters
    ----------

    vector : list
        A vector of parameters as produced by the Gibbs sampler,
        for example:

        ::

            [0, 0, 112]

    output_path : str
        The output path for the generated file.

    chain_definition
        The chain's definition object.
    """
    assert len(vector) == 3

    r, g, b = vector

    with open(output_path, "x") as file:
        file.write(fill_svg(r, g, b))
        file.close()
