# Vocabulary test demo

This demo shows the built-in `WikiVocab` and `BibleVocab` prescreen modules.
Participants classify words as real or fake across multiple languages.

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
git init
uv venv
source .venv/bin/activate
uv pip install -r constraints.txt
psynet scaffold
psynet test local
```
