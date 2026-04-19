#!/usr/bin/env python3
"""Check that all required modules import and Kokoro deps (misaki.en, spacy, num2words) are present.
Run from repo root with: python src/check_imports.py
Does not load ML models (no Metal/GPU required for this script).
"""
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

def main():
    errors = []
    # 1) Core app
    try:
        from src.improv_loop import ImprovSession
        from src.tts import MlxTts
        from src.stt import MlxStt
        from src.llm import MlxLlm
        from src.audio_io import AudioRecorder, AudioPlayer
        print("OK  app imports (improv_loop, tts, stt, llm, audio_io)")
    except Exception as e:
        errors.append(("app imports", e))

    # 2) misaki.en (required for Kokoro English G2P)
    try:
        from misaki import en
        g2p = en.G2P(trf=False, british=False, fallback=None)
        out, _ = g2p("hello")
        print("OK  misaki.en (spacy + num2words used by Kokoro English)")
    except Exception as e:
        errors.append(("misaki.en", e))

    # 3) num2words and spacy explicitly
    try:
        from num2words import num2words
        import spacy
        print("OK  num2words, spacy")
    except Exception as e:
        errors.append(("num2words/spacy", e))

    if errors:
        for name, e in errors:
            print(f"FAIL {name}: {e}", file=sys.stderr)
        sys.exit(1)
    print("\nAll import checks passed. Run 'python improv.py' to start (requires Metal/GPU).")
    return 0

if __name__ == "__main__":
    sys.exit(main())
