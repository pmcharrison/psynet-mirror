import os

from psynet.asset import CachedAsset
from psynet.trial.chain import ChainNode, ChainTrial


class Trial(ChainTrial):
    polymorphic_identity = "GenericTrial"


class Node(ChainNode):
    polymorphic_identity = "GenericNode"

    def summarize_trials(self, trials: list, experiment, participant):
        return None

    def create_definition_from_seed(self, seed, experiment, participant):
        return None


def compile_nodes_from_directory(
    input_dir: str,
    media_ext: str,
    node_class,
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
                        },
                        assets={
                            asset_label: CachedAsset(
                                input_path=media_path,
                                extension=media_ext,
                            )
                        },
                        participant_group=participant_group,
                        block=block,
                    )
                )
    return nodes
