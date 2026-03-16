# Dependencies and Kokoro (misaki / spacy)

## Are spacy and misaki[en] needed?

**Yes.** For Kokoro TTS with English (the only TTS backend in this app), both are required.

- **Kokoro pipeline** (`mlx_audio.tts.models.kokoro.pipeline`) does `from misaki import en, espeak` and, for American/British English (`lang_code` in `"ab"`), sets `self.g2p = en.G2P(...)`.
- **misaki.en** (`misaki/en.py`) imports **spacy** and **num2words** at module load. So loading Kokoro with English triggers `import misaki.en` → `import spacy` and use of num2words.
- **misaki[en]** is the extra that installs: `num2words`, `spacy`, `spacy-curated-transformers`, `phonemizer`. We also list **spacy** and **num2words** explicitly in `requirements.txt` so the stack is clear and installable even if someone installs `misaki` without the `[en]` extra.

So: **misaki[en]**, **spacy**, and **num2words** are all required for the app’s Kokoro English path. You cannot drop spacy or misaki[en] and keep Kokoro English working.

## Python version note

- On **Python 3.14**, spacy can hit a pydantic v1 compatibility issue (`ConfigError: unable to infer type for attribute "REGEX"`). If you see that, use **Python 3.10–3.12** for this project (e.g. `mamba create -n improv python=3.12`).
- **misaki** 0.9.x on PyPI currently targets Python &lt;3.13; if you are on 3.14 you may have 0.7.x and the same spacy/pydantic issue above applies.

## How to verify

From the repo root with the improv env activated:

```bash
python scripts/check_imports.py
```

Then run the app (needs Metal/GPU):

```bash
python improv.py --help
python improv.py
```
