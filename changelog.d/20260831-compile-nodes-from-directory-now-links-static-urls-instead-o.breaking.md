``compile_nodes_from_directory`` now requires media under ``static/`` and
stores ``/static/...`` URLs in the node definition instead of creating
``CachedAsset`` objects. Move files out of ``data/`` into ``static/`` and pass
``self.definition["prompt"]`` (or your ``asset_label``) to prompts.
