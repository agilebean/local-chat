#!/usr/bin/env python3
"""Voice-to-voice theatrical improv partner using local MLX models."""
# Patch pkg_resources for deps that require it (Python 3.12+ when setuptools is not installed)
try:
    import pkg_resources
except ModuleNotFoundError:
    import sys
    import types
    _pr = types.ModuleType("pkg_resources")
    _dist = type("Distribution", (), {"version": "0.0.0"})()
    _pr.get_distribution = lambda name: _dist
    _pr.require = lambda *a, **k: None
    _pr.working_set = []
    sys.modules["pkg_resources"] = _pr

import argparse
from src.improv_loop import ImprovSession


def main():
    parser = argparse.ArgumentParser(description="Real-time voice improv partner")
    parser.add_argument("-v", "--voice", default=None,
                        help=(
                            "Kokoro voice: af_heart (default), af_bella, af_nicole, af_sky, "
                            "am_adam, am_echo, am_liam, bf_emma, bf_isabella, bm_george, bm_lewis."
                        ))
    parser.add_argument("--llm", default="2b", choices=["0.8b", "2b", "4b", "qwen3"],
                        help="LLM variant: 0.8b, 2b (default), 4b (all Qwen3.5 MLX-4bit), or qwen3 (Qwen3-4B-Instruct-2507)")
    parser.add_argument("--ai-starts", action="store_true",
                        help="AI sets the scene on the first turn (default: human starts)")
    args = parser.parse_args()

    session = ImprovSession(voice=args.voice, ai_starts=args.ai_starts, llm_variant=args.llm, tts_backend="kokoro")
    session.run()


if __name__ == "__main__":
    main()
