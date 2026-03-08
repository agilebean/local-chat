#!/usr/bin/env python3
"""Voice-to-voice theatrical improv partner using local MLX models."""
import argparse
from src.improv_loop import ImprovSession
from src.tts import NEUTTS_VOICES


def main():
    parser = argparse.ArgumentParser(description="Real-time voice improv partner")
    parser.add_argument("--tts", default="kokoro", choices=["kokoro", "neutts-nano"],
                        help="TTS backend: kokoro (default, fast 82M) or neutts-nano (120M, voice cloning)")
    parser.add_argument("-v", "--voice", default=None,
                        help=(
                            "TTS voice preset. Kokoro (default af_heart): af_heart, af_bella, af_nicole, "
                            "af_sky, am_adam, am_echo, am_liam, bf_emma, bf_isabella, bm_george, bm_lewis. "
                            "NeuTTS-Nano (default jo): jo, dave, greta, juliette, mateo. "
                            "Passing a NeuTTS voice name auto-selects --tts neutts-nano."
                        ))
    parser.add_argument("--llm", default="2b", choices=["0.8b", "2b", "4b", "qwen3"],
                        help="LLM variant: 0.8b, 2b (default), 4b (all Qwen3.5 MLX-4bit), or qwen3 (Qwen3-4B-Instruct-2507)")
    parser.add_argument("--ai-starts", action="store_true",
                        help="AI sets the scene on the first turn (default: human starts)")
    args = parser.parse_args()

    tts_backend = args.tts
    if args.voice in NEUTTS_VOICES and tts_backend == "kokoro":
        tts_backend = "neutts-nano"

    session = ImprovSession(voice=args.voice, ai_starts=args.ai_starts, llm_variant=args.llm, tts_backend=tts_backend)
    session.run()


if __name__ == "__main__":
    main()
