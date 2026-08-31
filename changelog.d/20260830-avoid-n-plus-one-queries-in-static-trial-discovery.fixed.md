Sped up trial candidate discovery by batching viable-trial counts, skipping
those counts for unlimited unbalanced static nodes, and pairing static nodes
with their already-loaded networks so assignment no longer issues a network
query per candidate. ``TrialNode.n_viable_trials`` remains available in
SQLAlchemy filters and ordering without loading a cached count on every node.
