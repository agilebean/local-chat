#!/usr/bin/env python3
"""
Generate a spoken summary from a YouTube video (or local transcript) using
the **improv** environment only.

- Fetches the YouTube transcript with `youtube-transcript-api` (or reads a
  local `.txt` / `.md` file).
- Summarizes with improv's `MlxLlm` (Qwen3 MLX model).
- Synthesizes speech with improv's `MlxTts` (Kokoro-82M).

Usage:

    mamba activate improv
    python youtube/youtube_to_speech.py "YOUTUBE_URL_OR_FILE_PATH"

This script is fully self-contained inside the improv repo. There is no
dependency on the old `talk_to_tone` environment.
"""

import argparse
import sys
from pathlib import Path

from rich.console import Console

# Ensure repo root (which contains `src/`) is on sys.path so we can
# import improv modules when running this script directly.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.llm import MlxLlm
from src.tts import MlxTts
from youtube.youtube_scraper import get_video_transcript


console = Console()


def load_transcript_from_file(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return text.strip()


def is_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")


def summarize_transcript(transcript: str, target_words: int = 50) -> str:
    """Summarize transcript using improv's MlxLlm."""
    console.print("   Loading MLX model for summarization...", style="dim")
    llm = MlxLlm()
    llm.load()

    user_message = (
        f"Summarize this YouTube transcript in {target_words} words or less. "
        "Be concise and direct.\n\n"
        f"Transcript:\n{transcript[:2000]}"
    )
    messages = [{"role": "user", "content": user_message}]

    console.print("   Generating summary...", style="dim")
    summary = llm.generate(messages, max_tokens=80, temp=0.7).strip()
    return summary


def synthesize_speech(summary: str, output_dir: Path, voice: str | None = None) -> Path:
    """Use improv's MlxTts (Kokoro) to synthesize a speech.mp3 file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_path = output_dir / "speech.mp3"

    console.print(f"🎤 Using voice: {voice or 'af_heart'}", style="cyan")
    console.print("🎤 Generating speech with MLX-Audio (Kokoro)...", style="dim")

    tts = MlxTts()
    tts.load()
    tts.synthesize_to_file(summary, audio_path, voice=voice)
    console.print(f"✓ Saved speech to {audio_path}", style="green")
    return audio_path


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(description="YouTube → spoken summary (improv env).")
    parser.add_argument(
        "input",
        help="YouTube URL or path to a local .txt/.md transcript file.",
    )
    parser.add_argument(
        "-v",
        "--voice",
        default=None,
        help=(
            "Kokoro voice: af_heart (default), af_bella, af_nicole, af_sky, "
            "am_adam, am_echo, am_liam, bf_emma, bf_isabella, bm_george, bm_lewis."
        ),
    )
    parser.add_argument(
        "-w",
        "--words",
        type=int,
        default=50,
        help="Target word count for summary (default: 50).",
    )
    args = parser.parse_args(argv)

    inp = args.input
    input_path = Path(inp)

    try:
        if input_path.exists():
            console.print(f"📄 Using local transcript file: {input_path}", style="cyan")
            transcript = load_transcript_from_file(input_path)
            title = input_path.stem
        elif is_url(inp):
            video = get_video_transcript(inp)
            transcript = video.transcript
            # Use the scraper's title (e.g. \"Video_<id>\") rather than the raw
            # video ID so the folder name is a short, readable slug.
            title = video.title
        else:
            console.print("Input is neither a valid path nor a URL.", style="red")
            return 1

        if not transcript.strip():
            console.print("Transcript is empty.", style="red")
            return 1

        summary = summarize_transcript(transcript, target_words=args.words)
        console.print("\n📝 Summary:\n", style="bold")
        console.print(summary + "\n", style="white")

        # Folder name: 15–20 chars of a sanitized title, cut on whole words
        # where possible. Non-alphanumerics become underscores.
        sanitized = "".join(c if c.isalnum() else "_" for c in title)
        words = [w for w in sanitized.split("_") if w]
        max_len = 20
        target_min = 15
        slug = ""
        for w in words:
            candidate = (slug + "_" + w) if slug else w
            if len(candidate) > max_len:
                break
            slug = candidate
        if not slug:
            slug = sanitized[:max_len]
        elif len(slug) < target_min and len(sanitized) > len(slug):
            # Pad up to target_min if we ended up very short
            extra = sanitized[len(slug):target_min]
            slug = (slug + extra).rstrip("_")
        short_title = slug
        output_dir = Path("output") / short_title

        synthesize_speech(summary, output_dir, voice=args.voice)
        return 0
    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

