Sped up trial candidate discovery by batching viable-trial counts, skipping
those counts for unlimited unbalanced static nodes, and pairing static nodes
with their already-loaded networks so assignment no longer issues a network
query per candidate.
