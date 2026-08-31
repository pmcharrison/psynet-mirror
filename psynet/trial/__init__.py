import os
from pathlib import Path
from typing import Type, Union

from psynet.trial.chain import ChainNode, ChainTrial


class Trial(ChainTrial):
    pass


class Node(ChainNode):
    pass

    def summarize_trials(self, trials: list, experiment, participant):
        return None

    def create_definition_from_seed(self, seed, experiment, participant):
        return None


def static_url_for(
    path: Union[str, Path],
    *,
    experiment_root: Union[str, Path, None] = None,
) -> str:
    """Return the public ``/static/...`` URL for a file under ``static/``.

    Parameters
    ----------
    path
        File path, absolute or relative to the experiment directory.
    experiment_root
        Experiment directory. Defaults to the current working directory.
    """
    root = Path(experiment_root or Path.cwd()).resolve()
    static_root = (root / "static").resolve()
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = (root / resolved).resolve()
    try:
        relative = resolved.relative_to(static_root)
    except ValueError as exc:
        raise ValueError(
            f"{path} is not inside {static_root}. Put pregenerated media in "
            "static/ so it can be served as /static/..., or register the file "
            "as a PsyNet asset if it is generated or lives outside the experiment."
        ) from exc
    return "/static/" + relative.as_posix()


def compile_nodes_from_directory(
    input_dir: str,
    media_ext: str,
    node_class: Type[ChainNode],
    asset_label: str = "prompt",
):
    """Compile trial nodes from a directory of media files under ``static/``.

    This directory is expected to be structured in the following kind of way:

    input_dir/
    |-- participant_group_1/
    |   |-- block_1/
    |   |   |-- media_file_1.wav
    |   |   |-- media_file_2.wav
    |   |-- block_2/
    |   |   |-- media_file_3.wav
    |   |   |-- media_file_4.wav
    |   |-- block_3/
    |   |   |-- media_file_5.wav
    |   |   |-- media_file_6.wav
    |-- participant_group_2/
    |   |-- block_1/
    |   |   |-- media_file_7.wav
    |   |   |-- media_file_8.wav
    |   |-- block_2/
    |   |   |-- media_file_9.wav
    |   |   |-- media_file_10.wav
    |   |-- block_3/

    You can name the participant groups, blocks and files whatever you want; the important
    thing is their position in the hierarchy.

    Place ``input_dir`` under the experiment ``static/`` directory so the files
    are copied with the deployment plan and served as ``/static/...`` URLs.
    Each node definition stores that URL under ``asset_label`` (default
    ``"prompt"``). Pass ``self.definition["prompt"]`` to ``AudioPrompt``.

    Parameters
    ----------
    input_dir : str
        The path to the directory containing the media files.
    media_ext : str
        The extension of the media files.
    node_class : type
        The class of the node to compile.
    asset_label : str, optional
        Definition key that stores the media URL.

    Returns
    -------
    callable
        A lambda function ready to be passed to the ``nodes`` argument of a ``TrialMaker``.
        Don't evaluate this function before you pass it, the lazy evaluation is an important feature.
    """
    return lambda: _compile_nodes_from_directory(
        input_dir, media_ext, node_class, asset_label
    )


def _compile_nodes_from_directory(
    input_dir: str,
    media_ext: str,
    node_class: Type[ChainNode],
    asset_label: str = "prompt",
):
    nodes = []
    participant_groups = [(f.name, f.path) for f in os.scandir(input_dir) if f.is_dir()]
    for participant_group, group_path in participant_groups:
        blocks = [(f.name, f.path) for f in os.scandir(group_path) if f.is_dir()]
        for block, block_path in blocks:
            media_files = [
                (f.name, f.path)
                for f in os.scandir(block_path)
                if f.is_file() and f.path.endswith(media_ext)
            ]
            for media_name, media_path in media_files:
                nodes.append(
                    node_class(
                        definition={
                            "name": media_name,
                            asset_label: static_url_for(media_path),
                        },
                        participant_group=participant_group,
                        block=block,
                    )
                )
    return nodes
