# API demo

This demo shows how to expose Python functions and page methods via
`@expose_to_api`, then call them from front-end JavaScript in
`custom_pages.py`.

PsyNet demo directories track authored experiment files only. The unpinned
`psynet` requirement is resolved when a copied demo is set up.

Typical local workflow:

```bash
git init
uv venv --python 3.13
source .venv/bin/activate
uv pip install psynet
psynet setup
psynet debug local
```
