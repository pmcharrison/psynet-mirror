Stock experiment ``deploy.toml`` now uses ``exclude_anywhere`` for nested
junk names such as ``__pycache__`` and ``*.db``, keeping ``exclude`` for
root-relative prefixes like ``static/assets``.
