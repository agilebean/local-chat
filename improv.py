#!/usr/bin/env python3
"""Voice-to-voice theatrical improv partner using local MLX models."""
import argparse
from src.improv import ImprovSession


def main():
    parser = argparse.ArgumentParser(description="Real-time voice improv partner")
    parser.add_argument("-v", "--voice", default="ryan",
                        choices=["serena", "vivian", "uncle_fu", "ryan", "aiden",
                                 "ono_anna", "sohee", "eric", "dylan"],
                        help="TTS voice preset (default: ryan)")
    parser.add_argument("--voice-sample",
                        help="Path to voice sample for cloning (.wav/.mp3)")
    args = parser.parse_args()

    session = ImprovSession(voice=args.voice, ref_audio=args.voice_sample)
    session.run()


if __name__ == "__main__":
    main()
