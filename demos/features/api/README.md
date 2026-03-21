# API demo

This demo shows how to expose Python functions and page methods via
`@expose_to_api`, then call them from front-end JavaScript in
`custom_pages.py`.

The PsyNet demo directories include just the essential experiment files
(`experiment.py`, `requirements.txt`, `constraints.txt`) together with any
demo-specific helpers. If you copy this demo into your own workspace, generate
the additional boilerplate files with:

```bash
psynet scaffold
```

That command recreates files such as `Dockerfile`, `config.txt`, `test.py`,
`.gitignore`, and the `docker/` helper scripts.

Typical local workflow:

```bash
git init
uv venv
source .venv/bin/activate
uv pip install -r constraints.txt
psynet scaffold
psynet debug local
```
