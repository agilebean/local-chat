"""Local Text-to-Speech using MLX-Audio Qwen3-TTS."""
import os
os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'

import numpy as np
from pathlib import Path
from typing import Optional, Tuple


class MlxTts:
    """Wrapper around Qwen3-TTS loaded via mlx_audio.

    This class keeps the model resident in memory for efficient reuse
    across multiple synthesize() calls.
    """

    MODEL_ID = "mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit"

    def __init__(self):
        """Initialize the TTS wrapper."""
        self.model = None
        self.sample_rate = None

    def load(self):
        """Lazy-load TTS model (reuse across calls)."""
        if self.model is not None:
            return  # Already loaded

        from mlx_audio.tts.utils import load_model
        import warnings

        # Suppress the tokenizer regex warning
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*incorrect regex pattern.*")
            self.model = load_model(self.MODEL_ID)

        self.sample_rate = self.model.sample_rate

    def synthesize(
        self,
        text: str,
        voice: str = "vivian",
        ref_audio: Optional[str] = None
    ) -> Tuple[np.ndarray, int]:
        """Generate audio from text. Returns (audio_ndarray, sample_rate).

        Unlike generate_speech() in youtube_to_speech.py which saves to file,
        this returns raw audio data for flexible downstream use (file save OR playback).

        Args:
            text: Text to convert to speech.
            voice: Voice preset to use (default: vivian).
                  Available: serena, vivian, uncle_fu, ryan, aiden,
                            ono_anna, sohee, eric, dylan
            ref_audio: Optional path to a reference audio file for voice cloning.

        Returns:
            Tuple of (audio as numpy array, sample_rate)
        """
        if self.model is None:
            self.load()

        # Build kwargs for model.generate()
        kwargs = {"text": text, "verbose": False, "stream": False}

        if ref_audio:
            kwargs["ref_audio"] = ref_audio
        else:
            kwargs["voice"] = voice

        # Generate audio (returns a generator)
        results = self.model.generate(**kwargs)

        # Collect audio chunks
        audio_chunks = []
        for result in results:
            audio_chunks.append(result.audio)

        # Concatenate if multiple chunks
        if len(audio_chunks) > 1:
            import mlx.core as mx
            audio = mx.concatenate(audio_chunks, axis=0)
        else:
            audio = audio_chunks[0]

        # Convert to numpy array
        audio_np = np.array(audio)

        return audio_np, self.sample_rate

    def synthesize_to_file(
        self,
        text: str,
        output_path: Path,
        voice: str = "vivian",
        ref_audio: Optional[str] = None
    ) -> float:
        """Convenience: synthesize and save to file. Returns duration in seconds.

        This preserves the existing file-save behavior for backward compatibility.

        Args:
            text: Text to convert to speech.
            output_path: Path to save the audio file (MP3).
            voice: Voice preset to use.
            ref_audio: Optional path to reference audio for voice cloning.

        Returns:
            Duration of generated audio in seconds.
        """
        # Generate audio
        audio, sample_rate = self.synthesize(text, voice=voice, ref_audio=ref_audio)

        # Write to file as MP3
        from mlx_audio.audio_io import write as audio_write
        audio_write(str(output_path), audio, sample_rate, format="mp3")

        # Calculate duration
        duration = len(audio) / sample_rate

        return duration
