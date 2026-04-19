"""Suno AI Music Generator Adapter using AIMLAPI."""
import os
import time
import requests
from pathlib import Path
from rich.console import Console
from .base import MusicGenerator

console = Console()

class SunoMusicGenerator(MusicGenerator):
    """
    Adapter for Suno AI music generation using AIMLAPI.
    Requires AIML_API_KEY environment variable.
    """

    def __init__(self, api_key: str = None):
        """
        Initialize Suno generator via AIMLAPI.
        
        Args:
            api_key: AIMLAPI Key (or loaded from AIML_API_KEY env var).
        """
        self.api_key = api_key or os.getenv("AIML_API_KEY")
        # Using v2 endpoint which is common for AIMLAPI Suno integration
        self.base_url = "https://api.aimlapi.com/v2/generate/audio/suno-ai/clip"
        
        if not self.api_key:
             console.print("⚠️  AIML_API_KEY environment variable is missing!", style="red")
             console.print("   1. Go to https://aimlapi.com to get a key", style="dim")
             console.print("   2. Add to .env: AIML_API_KEY='your_key_here'", style="dim")

    def generate(self, prompt: str, output_path: Path, duration: float, instrumental: bool = False) -> float:
        """
        Generate music using Suno AI via AIMLAPI.

        Args:
            prompt: Description of the music.
            output_path: Path to save the audio.
            duration: Target duration.
            instrumental: If True, generates instrumental track.

        Returns:
            Actual duration.
        """
        if not self.api_key:
            raise ValueError("AIML_API_KEY is required. Please check your .env file.")

        console.print(f"🎵 Generating music with Suno AI (via AIMLAPI)...", style="cyan")
        console.print(f"   Prompt: {prompt}", style="dim")
        console.print(f"   Instrumental: {instrumental}", style="dim")

        # 1. Submit Generation Request
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # AIMLAPI payload structure
        payload = {
            "prompt": prompt,
            "make_instrumental": instrumental,
            "wait_audio": True  # Request synchronous waiting from the API
        }

        try:
            response = requests.post(self.base_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # AIMLAPI returns a list of clips or a specific structure depending on version
            # We handle potential variations safely
            clips = data.get("data") or data.get("clips") or []
            
            if not clips and isinstance(data, list):
                clips = data

            if not clips:
                 # Debug info if structure is unexpected
                 raise ValueError(f"No clips returned. API Response keys: {list(data.keys())}")

            # Pick the first clip
            clip = clips[0]
            audio_url = clip.get("audio_url") or clip.get("audio_path")
            
            if not audio_url:
                raise ValueError(f"No audio URL found in clip data: {clip.keys()}")

            console.print(f"   Downloading from: {audio_url}", style="dim")

            # 2. Download Audio
            audio_response = requests.get(audio_url)
            audio_response.raise_for_status()

            with open(output_path, 'wb') as f:
                f.write(audio_response.content)
            
            # Estimate duration (Suno V3 is typically ~120s)
            # We try to use pydub for accurate duration if available
            try:
                from pydub.utils import mediainfo
                info = mediainfo(str(output_path))
                duration_sec = float(info['duration'])
            except Exception:
                duration_sec = 120.0 # Default fallback if pydub fails or ffmpeg missing

            console.print(f"✓ Music generated: {duration_sec:.1f}s", style="green")
            return duration_sec

        except Exception as e:
            console.print(f"❌ Error using AIMLAPI: {e}", style="red")
            raise

