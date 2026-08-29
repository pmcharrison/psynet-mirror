Fixed Markdown display outputs being omitted from rendered audit notebooks.
The audit now renders ``text/markdown`` through the same sanitizer used for
Markdown sections, before falling back to ``text/plain``.
