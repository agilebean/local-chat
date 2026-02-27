#!/usr/bin/env python3
"""Voice-to-voice theatrical improv partner using local MLX models."""
import argparse
from src.improv_loop import ImprovSession


def main():
    parser = argparse.ArgumentParser(description="Real-time voice improv partner")
    parser.add_argument("-v", "--voice", default=None,
                        help=(
                            "TTS voice preset. Defaults to backend's default when omitted. "
                            "qwen3 voices: serena, vivian, uncle_fu, ryan, aiden, ono_anna, sohee, eric, dylan. "
                            "kokoro voices: af_heart, af_bella, af_nicole, af_sky, am_adam, am_echo, am_liam, "
                            "bf_emma, bf_isabella, bm_george, bm_lewis."
                        ))
    parser.add_argument("--voice-sample",
                        help="Path to voice sample for cloning (.wav/.mp3, qwen3 only)")
    parser.add_argument("--tts", default="kokoro", choices=["qwen3", "kokoro"],
                        help="TTS backend: kokoro (default, fast 82M params) or qwen3 (supports voice cloning)")
    parser.add_argument("--ai-starts", action="store_true",
                        help="AI sets the scene on the first turn (default: human starts)")
    args = parser.parse_args()

    session = ImprovSession(voice=args.voice, ref_audio=args.voice_sample, ai_starts=args.ai_starts, tts_backend=args.tts)
    session.run()


if __name__ == "__main__":
    main()
