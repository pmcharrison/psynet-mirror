# Vocabulary test demo

This demo shows the built-in `WikiVocab` and `BibleVocab` prescreen modules.
Participants classify words as real or fake across multiple languages.

PsyNet demo directories track authored experiment files only. The unpinned
`psynet` requirement is resolved when a copied demo is set up.

Typical local workflow:

```bash
git init
uv venv
source .venv/bin/activate
uv pip install psynet
psynet setup
psynet test local
```
