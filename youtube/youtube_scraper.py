"""YouTube transcript scraping functionality (ported from talk_to_tone)."""
import re
from dataclasses import dataclass
from typing import Optional

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
import requests
import html
from rich.console import Console


console = Console()


@dataclass
class YouTubeVideo:
    """Represents a YouTube video with transcript."""

    video_id: str
    title: str
    transcript: str
    url: str
    views: int = 0


def extract_video_id(url: str) -> Optional[str]:
    """
    Extract YouTube video ID from URL.

    Supports:
        - https://www.youtube.com/watch?v=VIDEO_ID
        - https://youtu.be/VIDEO_ID
        - https://www.youtube.com/embed/VIDEO_ID
        - https://m.youtube.com/watch?v=VIDEO_ID
        - raw 11-char video ID
    """
    patterns = [
        r"(?:v=|/)([0-9A-Za-z_-]{11}).*",
        r"youtu\.be/([0-9A-Za-z_-]{11})",
        r"embed/([0-9A-Za-z_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    # If URL is just the video ID
    if re.match(r"^[0-9A-Za-z_-]{11}$", url):
        return url

    return None


def get_video_transcript(video_url: str) -> YouTubeVideo:
    """
    Get transcript from a YouTube video.

    Raises ValueError with a clear message on failure.
    """
    console.print("🎥 Fetching YouTube transcript...", style="cyan")

    video_id = extract_video_id(video_url)
    if not video_id:
        raise ValueError(f"Invalid YouTube URL: {video_url}")

    console.print(f"   Video ID: {video_id}", style="dim")

    try:
        # Use the same API pattern as the original talk_to_tone scraper
        api = YouTubeTranscriptApi()
        fetched_transcript = api.fetch(video_id, languages=["en"])

        # Combine all transcript segments
        transcript_text = " ".join(
            [snippet.text for snippet in fetched_transcript.snippets]
        )

        transcript_text = clean_transcript(transcript_text)
        console.print(
            f"✓ Transcript fetched: {len(transcript_text)} characters", style="green"
        )

        video_url_clean = f"https://www.youtube.com/watch?v={video_id}"

        # Try to fetch the actual YouTube title for nicer folder names.
        try:
            resp = requests.get(video_url_clean, timeout=5)
            m = re.search(r"<title>(.*?)</title>", resp.text, re.IGNORECASE | re.DOTALL)
            if m:
                raw_title = html.unescape(m.group(1))
                raw_title = raw_title.replace("- YouTube", "").strip()
            else:
                raw_title = video_id
        except Exception:
            raw_title = video_id

        return YouTubeVideo(
            video_id=video_id,
            title=raw_title,
            transcript=transcript_text,
            url=video_url_clean,
        )

    except TranscriptsDisabled as e:
        console.print("❌ Transcripts are disabled for this video", style="red")
        raise ValueError("Transcripts disabled for this video") from e
    except NoTranscriptFound as e:
        console.print("❌ No transcript found for this video", style="red")
        raise ValueError("No transcript available (try a video with captions)") from e
    except Exception as e:
        console.print(f"❌ Error fetching transcript: {e}", style="red")
        raise ValueError(
            "Could not retrieve a transcript for this video. "
            "YouTube may be blocking requests from your IP or the video may lack captions."
        ) from e


def clean_transcript(text: str) -> str:
    """Light cleanup of transcript text."""
    # Remove [Music], [Applause], etc.
    text = re.sub(r"\[.*?\]", "", text)
    # Remove multiple spaces
    text = re.sub(r"\s+", " ", text)
    # Remove timestamps if any
    text = re.sub(r"\d{1,2}:\d{2}", "", text)
    return text.strip()


