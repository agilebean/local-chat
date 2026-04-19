#!/usr/bin/env python3
"""
Generate a spoken summary from a YouTube video (or local transcript) using
the **improv** environment only.

Three modes, layered on the same transcript → summary front-end:

1. **Speech only** (default): summarize and read aloud.
2. **Speech + background music** (`--genre` / `--music-prompt`): MLX MusicGen
   generates a short backing clip, ffmpeg loops it under the speech.
3. **Full vocal song** (`--song`): SunoAPI.org generates a ~2 min song whose
   lyrics are about the video's topic. Forces `--provider suno_org`.

Examples:

    mamba activate improv
    python youtube/youtube_to_speech.py URL                      # speech only
    python youtube/youtube_to_speech.py URL --genre jazz         # + background music
    python youtube/youtube_to_speech.py URL --song --genre pop   # full vocal song
"""

import argparse
import subprocess
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


console = Console()


# Same preset prompts the (now archived) talk_to_tone used. Keep them stable
# so old commands still produce comparable output.
GENRE_PROMPTS = {
    "romantic":   "romantic pop ballad, emotional, slow tempo",
    "taylorswift": "taylor swift style pop, catchy melody, modern production",
    "jazz":       "smooth jazz, saxophone, upright bass, relaxing",
    "drumbass":   "drum and bass electronic, fast tempo, energetic beats",
}

# Mix levels used when overlaying music under speech. Same defaults as
# talk_to_tone so existing recordings sound consistent.
MUSIC_VOLUME = 0.3
SPEECH_VOLUME = 0.55


def load_transcript_from_file(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def is_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")


def summarize_transcript(transcript: str, target_words: int = 50) -> str:
    """Summarize transcript using improv's MlxLlm. Single shot, light cleanup."""
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
    return llm.generate(messages, max_tokens=80, temp=0.7).strip()


# ---------- Aggressive summary cleanup (used only in --song mode) ----------
#
# YouTube transcripts are noisy (auto-captions, multiple speakers, no
# punctuation), and small Qwen models occasionally echo the prompt or wrap
# the answer in meta-commentary. For spoken summaries this is tolerable;
# for **song lyrics** it produces unusable input. The retry+scrub helpers
# below were salvaged from the (archived) talk_to_tone repo and are gated
# behind --song so the speech path stays simple.

_LEAD_MARKERS = (
    "**Summary", "Summary:", "This tutorial", "This video",
    "The video", "The transcript", "<|message|>",
)
_META_PHRASES = (
    "let's produce", "we need to", "let's do", "words or less",
    "craft a summary", "provide a", "≈", "words):",
)


def _extract_summary(text: str) -> str:
    """Strip prompt echo / meta-commentary; keep the actual summary body."""
    for marker in _LEAD_MARKERS:
        if marker in text:
            body = text[text.find(marker):]
            for token in ("<|end|>", "<|start|>", "<|message|>",
                          "**Summary**", "**", "Summary:"):
                body = body.replace(token, "")
            kept = [
                line.strip() for line in body.splitlines()
                if line.strip() and not any(p in line.lower() for p in _META_PHRASES)
            ]
            if kept:
                return " ".join(kept)
    return text


def _is_critically_bad(s: str, min_words: int = 5) -> bool:
    """Return True only for empty/garbage output worth retrying."""
    if len(s.strip()) < 5 or len(s.split()) < min_words:
        return True
    common = {"the", "a", "an", "is", "was", "are", "this", "that", "video", "tutorial"}
    return not any(w in s.lower() for w in common)


def _truncate_to_budget(s: str, max_sentences: int = 3, max_words: int = 50) -> str:
    sentences = s.split(". ")
    if len(sentences) > max_sentences:
        s = ". ".join(sentences[:max_sentences])
        if not s.endswith("."):
            s += "."
    words = s.split()
    if len(words) > max_words:
        s = " ".join(words[:max_words])
        if "." in s:
            s = s[:s.rfind(".") + 1]
    return s


def summarize_transcript_robust(
    transcript: str, target_words: int = 50, max_retries: int = 3,
) -> str:
    """Summarize with retries + scrubbing. Used as lyric input for --song mode."""
    console.print("   Loading MLX model for summarization...", style="dim")
    llm = MlxLlm()
    llm.load()
    user_message = (
        f"Summarize this YouTube transcript in {target_words} words or less. "
        "Be concise and direct.\n\n"
        f"Transcript:\n{transcript[:2000]}"
    )
    messages = [{"role": "user", "content": user_message}]

    last = ""
    for attempt in range(max_retries):
        if attempt:
            console.print(f"   Retry {attempt}/{max_retries - 1}...", style="dim yellow")
        raw = llm.generate(messages, max_tokens=80, temp=0.7).strip()
        cleaned = _extract_summary(raw)
        if cleaned.lower().startswith("summary:"):
            cleaned = cleaned[8:].strip()
        cleaned = cleaned.lstrip("\"'").strip()
        cleaned = " ".join(cleaned.split())
        cleaned = _truncate_to_budget(cleaned)
        last = cleaned
        if not _is_critically_bad(cleaned) and len(cleaned.split()) >= 15:
            return cleaned
    console.print("   Warning: using last attempt despite low quality.", style="yellow")
    return last


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


# ---------- Background-music pipeline (opt-in) ----------

def get_audio_duration(path: Path) -> float:
    """Return duration in seconds via `ffprobe` (fast metadata read)."""
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def generate_background_music(
    prompt: str, output_path: Path, duration_seconds: float, provider: str = "mlx",
) -> float:
    """Generate `duration_seconds` of music to `output_path` via the chosen provider.

    `mlx` is local (Apple Silicon, free); `suno_org` is remote (paid, requires
    SUNO_ORG_KEY). Vocals are forced off for background use.
    """
    from src.music import get_music_generator

    music_gen = get_music_generator(provider)
    return music_gen.generate(
        prompt=prompt,
        output_path=output_path,
        duration=duration_seconds,
        instrumental=True,
    )


def merge_speech_with_music(
    speech_path: Path, music_path: Path, output_path: Path,
) -> float:
    """Loop music to cover speech length, mix at fixed levels, write merged MP3.

    Returns the merged-clip duration (= speech duration).
    """
    speech_dur = get_audio_duration(speech_path)
    music_dur = get_audio_duration(music_path)

    if music_dur < speech_dur:
        loops_needed = int(speech_dur / music_dur) + 1
        console.print(f"   Looping music {loops_needed}× to cover {speech_dur:.1f}s of speech",
                      style="dim")
        # `aloop=size=2e9` is just a large per-iteration sample budget so
        # short clips can loop many times without truncation.
        music_filter = (
            f"[0:a]aloop=loop={loops_needed}:size=2e9,"
            f"atrim=0:{speech_dur},volume={MUSIC_VOLUME}[music]"
        )
        amix_dur = "shortest"
    else:
        music_filter = f"[0:a]volume={MUSIC_VOLUME}[music]"
        amix_dur = "first"

    filter_complex = (
        f"{music_filter};"
        f"[1:a]volume={SPEECH_VOLUME}[speech];"
        f"[music][speech]amix=inputs=2:duration={amix_dur}"
    )

    console.print("   Mixing speech over music with ffmpeg...", style="dim")
    subprocess.run(
        ["ffmpeg",
         "-i", str(music_path),
         "-i", str(speech_path),
         "-filter_complex", filter_complex,
         "-c:a", "libmp3lame", "-q:a", "5",  # ~130 kbps VBR; fast
         "-y", str(output_path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
    )
    return speech_dur


def _load_env_file(path: Path = REPO_ROOT / ".env") -> None:
    """Minimal .env loader (KEY=VALUE per line, # comments, optional quotes).

    Avoids a `python-dotenv` dependency for one feature. Existing process
    env wins — `setdefault` semantics, same as dotenv's `override=False`.
    """
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip().strip('"').strip("'")
        import os
        os.environ.setdefault(k.strip(), v)


def generate_song(
    summary: str, output_dir: Path, *, genre: str | None = None,
    duration_seconds: float = 120.0,
) -> Path:
    """Generate a full vocal song about the summary topic via SunoAPI.org.

    MLX MusicGen can't do vocals (`mlx_adapter.py` forces instrumental), so
    this path is hard-wired to `suno_org` regardless of `--provider`.
    Truncates the topic to 200 chars to stay inside Suno's prompt budget.
    """
    _load_env_file()
    from src.music import get_music_generator

    style = genre or "pop"
    topic = f"A {style} song about: {summary}"
    if len(topic) > 200:
        topic = topic[:197] + "..."

    output_dir.mkdir(parents=True, exist_ok=True)
    song_path = output_dir / "song.mp3"

    console.print(f"\n🎤 Generating full vocal song ({style}) via SunoAPI.org",
                  style="cyan")
    console.print(f"   Topic: {topic}", style="dim")

    music_gen = get_music_generator("suno_org")
    music_gen.generate(
        prompt=topic, output_path=song_path,
        duration=duration_seconds, instrumental=False,
    )
    console.print(f"✓ Song saved: {song_path}", style="green")
    return song_path


def add_background_music(
    speech_path: Path, output_dir: Path, *,
    prompt: str, provider: str, music_seconds: float,
) -> Path:
    """End-to-end: generate music, merge under speech. Returns merged MP3 path."""
    music_wav = output_dir / "_music_raw.wav"
    music_mp3 = output_dir / "music.mp3"
    merged = output_dir / f"speech_on_music.mp3"

    console.print(f"\n🎵 Generating {music_seconds:.0f}s of background music ({provider})",
                  style="cyan")
    console.print(f"   Prompt: {prompt}", style="dim")
    generate_background_music(prompt, music_wav, music_seconds, provider=provider)

    # Save a clean MP3 of the looped/trimmed music so the user can re-use it.
    speech_dur = get_audio_duration(speech_path)
    music_dur = get_audio_duration(music_wav)
    if music_dur < speech_dur:
        loops_needed = int(speech_dur / music_dur) + 1
        loop_filter = f"aloop=loop={loops_needed}:size=2e9,atrim=0:{speech_dur}"
    else:
        loop_filter = f"atrim=0:{speech_dur}"
    subprocess.run(
        ["ffmpeg", "-i", str(music_wav), "-af", loop_filter,
         "-c:a", "libmp3lame", "-q:a", "5", "-y", str(music_mp3)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
    )

    merge_speech_with_music(speech_path, music_wav, merged)
    music_wav.unlink(missing_ok=True)

    console.print(f"✓ Merged: {merged}", style="green")
    return merged


# ---------- CLI ----------

def slugify_title(title: str, max_len: int = 20, target_min: int = 15) -> str:
    """15–20 char folder slug, preferring whole-word boundaries."""
    sanitized = "".join(c if c.isalnum() else "_" for c in title)
    words = [w for w in sanitized.split("_") if w]
    slug = ""
    for w in words:
        candidate = (slug + "_" + w) if slug else w
        if len(candidate) > max_len:
            break
        slug = candidate
    if not slug:
        return sanitized[:max_len]
    if len(slug) < target_min and len(sanitized) > len(slug):
        slug = (slug + sanitized[len(slug):target_min]).rstrip("_")
    return slug


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        description="YouTube → spoken summary (+ optional background music)."
    )
    parser.add_argument("input",
                        help="YouTube URL or path to a local .txt/.md transcript file.")
    parser.add_argument("--voice", "-v", default=None,
                        help="Kokoro voice (af_heart default; see README).")
    parser.add_argument("--words", "-w", type=int, default=50,
                        help="Target word count for the summary (default: 50).")

    # --- Background music (opt-in) ---
    parser.add_argument("--genre", "-g", choices=sorted(GENRE_PROMPTS),
                        help="Add background music using a preset style "
                             f"({', '.join(sorted(GENRE_PROMPTS))}). "
                             "In --song mode this becomes the song's style.")
    parser.add_argument("--music-prompt",
                        help="Custom music style prompt (overrides --genre).")
    parser.add_argument("--music-seconds", type=float, default=7.0,
                        help="Length of the generated music clip in seconds; "
                             "looped to cover the speech (default: 7).")
    parser.add_argument("--provider", "-p", choices=["mlx", "suno_org"], default="mlx",
                        help="Music backend: mlx (local, default) or suno_org "
                             "(remote, needs SUNO_ORG_KEY). --song forces suno_org.")

    # --- Full vocal song (opt-in, mutually exclusive with background music) ---
    parser.add_argument("--song", action="store_true",
                        help="Generate a full vocal song (~2 min) about the "
                             "video topic via SunoAPI.org. Skips speech + "
                             "background-music output.")
    parser.add_argument("--song-seconds", type=float, default=120.0,
                        help="Target song length in seconds (default: 120).")
    args = parser.parse_args(argv)

    if args.song and args.provider == "mlx":
        console.print(
            "ℹ️  --song requires Suno (vocals); switching --provider to suno_org.",
            style="dim",
        )
        args.provider = "suno_org"

    # Resolve transcript ----------------------------------------------------
    inp = args.input
    input_path = Path(inp)
    try:
        if input_path.exists():
            console.print(f"📄 Using local transcript file: {input_path}", style="cyan")
            transcript = load_transcript_from_file(input_path)
            title = input_path.stem
        elif is_url(inp):
            from youtube.youtube_scraper import get_video_transcript
            video = get_video_transcript(inp)
            transcript = video.transcript
            title = video.title
        else:
            console.print("Input is neither a valid path nor a URL.", style="red")
            return 1

        if not transcript.strip():
            console.print("Transcript is empty.", style="red")
            return 1

        output_dir = Path("output") / slugify_title(title)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Summary -----------------------------------------------------------
        # --song uses lyric-quality input → robust path with retries+scrub.
        # Other modes feed Kokoro, which handles minor noise gracefully.
        if args.song:
            summary = summarize_transcript_robust(transcript, target_words=args.words)
        else:
            summary = summarize_transcript(transcript, target_words=args.words)
        console.print("\n📝 Summary:\n", style="bold")
        console.print(summary + "\n", style="white")
        (output_dir / "summary.txt").write_text(summary, encoding="utf-8")

        # Branch: full vocal song (Suno) -----------------------------------
        if args.song:
            generate_song(
                summary, output_dir,
                genre=args.genre, duration_seconds=args.song_seconds,
            )
            console.print(f"\n📁 Output: {output_dir}/", style="bold cyan")
            return 0

        # Default branch: speech (+ optional background music) -------------
        speech_path = synthesize_speech(summary, output_dir, voice=args.voice)
        if args.genre or args.music_prompt:
            prompt = args.music_prompt or GENRE_PROMPTS[args.genre]
            add_background_music(
                speech_path, output_dir,
                prompt=prompt, provider=args.provider,
                music_seconds=args.music_seconds,
            )

        console.print(f"\n📁 Output: {output_dir}/", style="bold cyan")
        return 0

    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
