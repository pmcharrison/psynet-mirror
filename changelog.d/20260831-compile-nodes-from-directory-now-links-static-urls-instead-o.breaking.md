``compile_nodes_from_directory`` now requires media under ``static/`` and
stores ``/static/...`` URLs in the node definition instead of creating
``CachedAsset`` objects. Move files out of ``data/`` into ``static/`` and pass
``self.definition["url"]`` (or your ``url_key``) to prompts. Directories
outside ``static/`` (including paths outside the experiment) are no longer
supported. The old ``asset_label`` argument was the CachedAsset dictionary
key; ``url_key`` is the definition key for that URL. Media extensions are
matched case-insensitively. Nodes are compiled in alphabetical order by
participant group, block, and filename.
