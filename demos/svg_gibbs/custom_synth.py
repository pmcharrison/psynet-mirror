
def fill_svg(r, g, b):
    svg =  (f'<svg xmlns="http://www.w3.org/2000/svg" width="250" height="250">' 
            f'<rect width="250" height="250" style="fill:rgb({r},{g},{b});" >' 
            f'<animate attributeName="fill" begin="2s" calcMode="linear" dur="5s" '
            f'repeatCount="indefinite" values="rgb({r},{g},{b});white;rgb({r},{g},{b})"></animate>'
            f'</rect>'
            f'Sorry, your browser does not support inline SVG.' 
            f'</svg>'
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

    file = open(output_path, "x")
    file.write(fill_svg(r, g, b))
    file.close()