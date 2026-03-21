# Vocabulary test demo

This demo shows the built-in `WikiVocab` and `BibleVocab` prescreen modules.
Participants classify words as real or fake across multiple languages.

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
psynet test local
```
