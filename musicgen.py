#!/usr/bin/env python3
"""Generate background music with MLX MusicGen (local, Apple Silicon).

Salvaged from the (now-archived) talk_to_tone repo. The vendored MLX MusicGen
library lives in `src/music/musicgen/` and is loaded lazily by the adapter,
so importing this script doesn't trigger a multi-second model load.
"""
import argparse
from pathlib import Path

from src.music import get_music_generator

MODEL_CHOICES = {
    "small": "facebook/musicgen-small",
    "medium": "facebook/musicgen-medium",
    "large": "facebook/musicgen-large",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "prompt",
        help='Text description, e.g. "lo-fi hip hop with vinyl crackle"',
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("output/music.wav"),
        help="Output .wav path (default: output/music.wav)",
    )
    parser.add_argument(
        "-d", "--duration",
        type=float,
        default=10.0,
        help="Length in seconds (default: 10)",
    )
    parser.add_argument(
        "-m", "--model",
        choices=MODEL_CHOICES.keys(),
        default="small",
        help="MusicGen size: small (default), medium, large",
    )
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)

    gen = get_music_generator("mlx", model=MODEL_CHOICES[args.model])
    gen.generate(args.prompt, args.output, duration=args.duration)


if __name__ == "__main__":
    main()
