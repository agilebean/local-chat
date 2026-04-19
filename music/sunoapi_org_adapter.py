"""SunoAPI.org Music Generator Adapter."""
import os
import time
import requests
from pathlib import Path
from rich.console import Console
from .base import MusicGenerator

console = Console()

class SunoApiOrgGenerator(MusicGenerator):
    """
    Adapter for Suno AI music generation using SunoAPI.org.
    Requires SUNO_ORG_KEY environment variable.
    """

    def __init__(self, api_key: str = None):
        """
        Initialize Suno generator via SunoAPI.org.
        
        Args:
            api_key: SunoAPI.org Key (or loaded from SUNO_ORG_KEY env var).
        """
        self.api_key = api_key or os.getenv("SUNO_ORG_KEY")
        self.base_url = "https://api.sunoapi.org/api/v1"
        
        if not self.api_key:
             console.print("⚠️  SUNO_ORG_KEY environment variable is missing!", style="red")
             console.print("   1. Go to https://sunoapi.org to get a key", style="dim")
             console.print("   2. Add to .env: SUNO_ORG_KEY='your_key_here'", style="dim")

    def generate(self, prompt: str, output_path: Path, duration: float, instrumental: bool = False) -> float:
        """
        Generate music using Suno via SunoAPI.org.

        Args:
            prompt: Description of the music.
            output_path: Path to save the audio.
            duration: Target duration.
            instrumental: If True, generates instrumental track.

        Returns:
            Actual duration.
        """
        if not self.api_key:
            raise ValueError("SUNO_ORG_KEY is required. Please check your .env file.")

        console.print(f"🎵 Generating music with Suno (via SunoAPI.org)...", style="cyan")
        console.print(f"   Prompt: {prompt}", style="dim")
        console.print(f"   Instrumental: {instrumental}", style="dim")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # 1. Submit Generation Request
        # Documentation suggests 'customMode': false for simple prompts
        payload = {
            "prompt": prompt,
            "customMode": False,
            "instrumental": instrumental, 
            "model": "V3_5",
            "callBackUrl": "https://example.com/callback" # Added placeholder to satisfy API requirement
        }

        try:
            response = requests.post(f"{self.base_url}/generate", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # Extract Task ID
            task_id = data.get("taskId")
            
            # Check nested "data" object safely
            if not task_id:
                inner_data = data.get("data")
                if inner_data:
                    task_id = inner_data.get("taskId")
            
            if not task_id:
                raise ValueError(f"No taskId in response: {data}")

            console.print(f"   Task ID: {task_id}. Polling for completion...", style="dim")

            # 2. Poll for Completion
            audio_url = None
            # Increase timeout to ~7.5 minutes (150 attempts * 3s)
            for i in range(150): 
                time.sleep(3)
                
                status_resp = requests.get(
                    f"{self.base_url}/generate/record-info?taskId={task_id}",
                    headers=headers
                )
                
                if status_resp.status_code != 200:
                    console.print(f"   Polling error: {status_resp.status_code}", style="dim red")
                    continue
                    
                status_data = status_resp.json()
                # Check status structure. Typically {"data": {"status": "SUCCESS", "response": {"audio_url": "..."}}}
                
                # Normalize data access
                inner_data = status_data.get("data", status_data)
                status = inner_data.get("status")
                
                if status == "SUCCESS":
                    # Find audio URL in the specific structure returned by SunoAPI.org
                    response_info = inner_data.get("response")
                    
                    if isinstance(response_info, dict):
                        suno_data = response_info.get("sunoData")
                        if isinstance(suno_data, list) and len(suno_data) > 0:
                            clip = suno_data[0]
                            audio_url = clip.get("audioUrl") or clip.get("audio_url") or clip.get("streamAudioUrl")

                    # Fallback to previous extraction logic if still not found
                    if not audio_url:
                        if isinstance(response_info, list) and len(response_info) > 0:
                            clip = response_info[0]
                            audio_url = clip.get("audio_url") or clip.get("audio_path") or clip.get("audioUrl")
                        elif isinstance(response_info, dict):
                            audio_url = audio_url or response_info.get("audio_url") or response_info.get("audioUrl")
                    
                    if not audio_url:
                        audio_url = inner_data.get("audioUrl") or inner_data.get("audio_url")

                    if audio_url:
                        break
                elif status == "FAILED":
                    raise RuntimeError(f"Generation failed: {inner_data}")
                
                # If still processing (PENDING/TEXT_PROCESSING/etc), continue
                if i % 5 == 0:
                    console.print(f"   Status: {status}...", style="dim")

            if not audio_url:
                raise TimeoutError("Timed out waiting for audio generation.")

            console.print(f"   Downloading from: {audio_url}", style="dim")

            # 3. Download Audio
            audio_response = requests.get(audio_url)
            audio_response.raise_for_status()

            with open(output_path, 'wb') as f:
                f.write(audio_response.content)
            
            # Estimate duration
            try:
                from pydub.utils import mediainfo
                info = mediainfo(str(output_path))
                duration_sec = float(info['duration'])
            except Exception:
                duration_sec = 120.0 

            console.print(f"✓ Music generated: {duration_sec:.1f}s", style="green")
            return duration_sec

        except Exception as e:
            # Removed redundant console.print here
            raise
