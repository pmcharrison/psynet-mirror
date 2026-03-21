# API demo

This demo shows how to expose Python functions and page methods via
`@expose_to_api`, then call them from front-end JavaScript in
`custom_pages.py`.

This directory intentionally keeps only the authored demo files plus
`requirements.txt`, `constraints.txt`, and this README. If you copy it into
your own workspace, generate the usual PsyNet boilerplate with:

```bash
psynet scaffold
```

That command recreates files such as `Dockerfile`, `config.txt`, `test.py`,
`.gitignore`, and the `docker/` helper scripts.

Typical local workflow:

```bash
uv venv
source .venv/bin/activate
uv pip install -r constraints.txt
psynet scaffold
psynet debug local
```
