Fixed matplotlib plots rendering as solid black blocks in audit sites. The
notebook SVG sanitizer discarded the ``defs``/``use`` glyph references,
``transform``, ``clip-path``, and inline ``style`` declarations that the plots
depend on. Those are now preserved, while external references and
non-presentation CSS are still removed.
