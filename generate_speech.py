#!/usr/bin/env python3
"""Generate speech from a YouTube video or local text file, with optional background music.

Input is auto-detected:
  - YouTube URL  → transcript fetched via youtube/youtube_scraper.py
  - File path    → read directly as text

Three output modes:

1. Speech only (default): summarize → Kokoro reads it aloud.
2. Speech + background music (--genre / --music-prompt): MLX MusicGen generates
   a backing clip, ffmpeg loops it under the speech.
3. Full vocal song (--song): SunoAPI.org generates a ~2 min vocal song.

Usage:
    python generate_speech.py YOUTUBE_URL
    python generate_speech.py YOUTUBE_URL --genre jazz
    python generate_speech.py transcript.txt --genre kpop
    python generate_speech.py --help
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from rich.console import Console

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.llm import MlxLlm
from src.tts import MlxTts

console = Console()

GENRE_PROMPTS = {
    "drumbass":    "drum and bass electronic, fast tempo, energetic beats",
    "jazz":        "smooth jazz, saxophone, upright bass, relaxing",
    "kpop":        "K-pop, bright synth pop, punchy beat, catchy hook, Korean idol style",
    "romantic":    "romantic pop ballad, emotional, slow tempo",
    "taylorswift": "taylor swift style pop, catchy melody, modern production",
}

MUSIC_VOLUME = 0.15   # background bed; sum with speech peaks at 1.0
SPEECH_VOLUME = 0.85  # foreground narration; clearly audible over music


# ---------- Input resolution ----------

def is_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")


def resolve_input(inp: str) -> tuple[str, str]:
    """Return (text, title) from a YouTube URL or a local text file path.

    Only calls the youtube module when the input is actually a URL.
    """
    if is_url(inp):
        from src.youtube_scraper import get_video_transcript
        video = get_video_transcript(inp)
        return video.transcript, video.title
    path = Path(inp)
    if path.exists():
        return path.read_text(encoding="utf-8").strip(), path.stem
    console.print(f"[red]Input not found:[/red] '{inp}' is not a URL and no file exists at that path.")
    raise SystemExit(1)


# ---------- Summarisation ----------

def summarize_transcript(transcript: str, target_words: int = 50) -> str:
    """Single-shot summary via local LLM. Light cleanup only."""
    console.print("   Loading MLX model for summarization...", style="dim")
    llm = MlxLlm()
    llm.load()
    messages = [{"role": "user", "content": (
        f"Summarize this transcript in {target_words} words or less. "
        f"Be concise and direct.\n\nTranscript:\n{transcript[:2000]}"
    )}]
    console.print("   Generating summary...", style="dim")
    return llm.generate(messages, max_tokens=80, temp=0.7).strip()


# -- Robust summarisation (--song only) --
# YouTube transcripts are noisy and small LLMs occasionally echo the prompt.
# For Kokoro speech this is tolerable; for Suno lyrics it produces unusable
# input. The retry+scrub path below is therefore gated to --song only.

_LEAD_MARKERS = (
    "**Summary", "Summary:", "This tutorial", "This video",
    "The video", "The transcript", "<|message|>",
)
_META_PHRASES = (
    "let's produce", "we need to", "let's do", "words or less",
    "craft a summary", "provide a", "≈", "words):",
)


def _extract_summary(text: str) -> str:
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
    """Summary with retries + scrubbing. Used as lyric input for --song mode."""
    console.print("   Loading MLX model for summarization...", style="dim")
    llm = MlxLlm()
    llm.load()
    messages = [{"role": "user", "content": (
        f"Summarize this transcript in {target_words} words or less. "
        f"Be concise and direct.\n\nTranscript:\n{transcript[:2000]}"
    )}]
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


# ---------- Speech synthesis ----------

def synthesize_speech(summary: str, output_dir: Path, voice: str = "af_heart") -> Path:
    """Synthesize summary to speech.mp3 via Kokoro."""
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_path = output_dir / "speech.mp3"
    console.print(f"🎤 Using voice: {voice}", style="cyan")
    console.print("🎤 Generating speech with MLX-Audio (Kokoro)...", style="dim")
    tts = MlxTts()
    tts.load()
    tts.synthesize_to_file(summary, audio_path, voice=voice)
    console.print(f"✓ Saved speech to {audio_path}", style="green")
    return audio_path


# ---------- Background music ----------

def get_audio_duration(path: Path) -> float:
    """Return duration in seconds via ffprobe."""
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def generate_background_music(
    prompt: str, output_path: Path, duration_seconds: float, provider: str = "mlx",
) -> float:
    """Generate instrumental music via the chosen provider (mlx or suno_org)."""
    from music import get_music_generator
    return get_music_generator(provider).generate(
        prompt=prompt, output_path=output_path,
        duration=duration_seconds, instrumental=True,
    )


def merge_speech_with_music(
    speech_path: Path, music_path: Path, output_path: Path,
) -> float:
    """Loop music to cover speech length, mix at fixed levels, write merged MP3.

    normalize=0 keeps volumes as specified; the default normalize=1 would
    halve both streams (÷2 for 2 inputs), making speech inaudibly quiet.
    """
    speech_dur = get_audio_duration(speech_path)
    music_dur = get_audio_duration(music_path)

    if music_dur < speech_dur:
        loops_needed = int(speech_dur / music_dur) + 1
        console.print(f"   Looping music {loops_needed}× to cover {speech_dur:.1f}s", style="dim")
        # size=2e9: large per-iteration sample budget so short clips can loop many times
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
        f"[music][speech]amix=inputs=2:duration={amix_dur}:normalize=0"
    )
    console.print("   Mixing speech over music with ffmpeg...", style="dim")
    subprocess.run(
        ["ffmpeg", "-i", str(music_path), "-i", str(speech_path),
         "-filter_complex", filter_complex,
         "-c:a", "libmp3lame", "-q:a", "5", "-y", str(output_path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
    )
    return speech_dur


def add_background_music(
    speech_path: Path, output_dir: Path, *,
    prompt: str, provider: str, music_seconds: float,
) -> Path:
    """Generate music, save music.mp3, merge with speech. Returns merged path."""
    music_wav = output_dir / "_music_raw.wav"
    music_mp3 = output_dir / "music.mp3"
    merged = output_dir / "speech_on_music.mp3"

    console.print(f"\n🎵 Generating {music_seconds:.0f}s of background music ({provider})", style="cyan")
    console.print(f"   Prompt: {prompt}", style="dim")
    generate_background_music(prompt, music_wav, music_seconds, provider=provider)

    speech_dur = get_audio_duration(speech_path)
    music_dur = get_audio_duration(music_wav)
    loop_filter = (
        f"aloop=loop={int(speech_dur / music_dur) + 1}:size=2e9,atrim=0:{speech_dur}"
        if music_dur < speech_dur else f"atrim=0:{speech_dur}"
    )
    subprocess.run(
        ["ffmpeg", "-i", str(music_wav), "-af", loop_filter,
         "-c:a", "libmp3lame", "-q:a", "5", "-y", str(music_mp3)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
    )
    merge_speech_with_music(speech_path, music_wav, merged)
    music_wav.unlink(missing_ok=True)
    console.print(f"✓ Merged: {merged}", style="green")
    return merged


# ---------- Vocal song (Suno, --song mode) ----------

def _load_env_file(path: Path = REPO_ROOT / ".env") -> None:
    """Minimal .env loader. Existing env vars win (setdefault semantics)."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def generate_song(
    summary: str, output_dir: Path, *, genre: str | None = None,
    duration_seconds: float = 120.0,
) -> Path:
    """Generate a full vocal song via SunoAPI.org.

    MLX MusicGen is instrumental-only, so this path hard-wires suno_org.
    Topic is capped at 200 chars to stay inside Suno's prompt budget.
    """
    _load_env_file()
    from music import get_music_generator

    style = genre or "pop"
    topic = f"A {style} song about: {summary}"
    if len(topic) > 200:
        topic = topic[:197] + "..."

    output_dir.mkdir(parents=True, exist_ok=True)
    song_path = output_dir / "song.mp3"
    console.print(f"\n🎤 Generating full vocal song ({style}) via SunoAPI.org", style="cyan")
    console.print(f"   Topic: {topic}", style="dim")
    get_music_generator("suno_org").generate(
        prompt=topic, output_path=song_path,
        duration=duration_seconds, instrumental=False,
    )
    console.print(f"✓ Song saved: {song_path}", style="green")
    return song_path


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
    parser = argparse.ArgumentParser(
        description="Generate speech from a YouTube URL or text file, with optional background music."
    )
    parser.add_argument("input",
                        help="YouTube URL or path to a local text file.")
    parser.add_argument("--voice", "-v", default="af_heart",
                        choices=["af_heart", "bm_george"],
                        help="Kokoro voice (default: af_heart).")
    parser.add_argument("--words", "-w", type=int, default=50,
                        help="Target word count for the summary (default: 50).")
    parser.add_argument("--genre", "-g", choices=sorted(GENRE_PROMPTS),
                        help="MusicGen background music style "
                             f"({', '.join(sorted(GENRE_PROMPTS))}). "
                             "Also sets Suno song style when --song is given.")
    parser.add_argument("--music-prompt",
                        help="Custom MusicGen style description (overrides --genre).")
    parser.add_argument("--music-seconds", type=float, default=7.0,
                        help="Length of the generated backing clip in seconds (default: 7).")
    parser.add_argument("--provider", "-p", choices=["mlx", "suno_org"], default="mlx",
                        help="Music backend: mlx (local, default) or suno_org "
                             "(remote, needs SUNO_ORG_KEY). --song forces suno_org.")
    parser.add_argument("--song", action="store_true",
                        help="Generate a full vocal song via SunoAPI.org instead of speech.")
    parser.add_argument("--song-seconds", type=float, default=120.0,
                        help="Target song length in seconds (default: 120).")
    args = parser.parse_args(argv)

    if args.song and args.provider == "mlx":
        console.print("ℹ️  --song requires Suno (vocals); switching --provider to suno_org.", style="dim")
        args.provider = "suno_org"

    try:
        transcript, title = resolve_input(args.input)
        if not transcript.strip():
            console.print("Input is empty.", style="red")
            return 1

        output_dir = Path("output") / slugify_title(title)
        output_dir.mkdir(parents=True, exist_ok=True)

        # --song needs clean lyric input; speech mode tolerates noisy transcripts
        summary = (
            summarize_transcript_robust(transcript, target_words=args.words)
            if args.song else
            summarize_transcript(transcript, target_words=args.words)
        )
        console.print("\n📝 Summary:\n", style="bold")
        console.print(summary + "\n", style="white")
        (output_dir / "summary.txt").write_text(summary, encoding="utf-8")

        if args.song:
            generate_song(summary, output_dir, genre=args.genre, duration_seconds=args.song_seconds)
        else:
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
        console.print(f"❌ {e}", style="red")
        return 1


if __name__ == "__main__":
    sys.exit(main())
