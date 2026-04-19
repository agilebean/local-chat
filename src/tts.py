"""Local Text-to-Speech using MLX-Audio (Kokoro)."""
import os
os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'

import time
import numpy as np
from pathlib import Path
from typing import Optional, Tuple


KOKORO_MODEL_ID = "mlx-community/Kokoro-82M-bf16"
KOKORO_VOICES = ["af_heart", "bm_george"]
KOKORO_DEFAULT_VOICE = "af_heart"

KOKORO_VOICE_DESCRIPTIONS = {
    "af_heart":  "feminine light",
    "bm_george": "masculine elder, approachable",
}


class MlxTts:
    """Wrapper around mlx_audio Kokoro TTS model."""

    def __init__(self):
        self.model_id = KOKORO_MODEL_ID
        self.default_voice = KOKORO_DEFAULT_VOICE
        self.model = None
        self.sample_rate = None
        self.last_latency_s: float = 0.0  # time to first audio chunk from last synthesize()

    def load(self):
        """Lazy-load TTS model (reuse across calls)."""
        if self.model is not None:
            return

        from mlx_audio.tts.utils import load_model
        import warnings

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*incorrect regex pattern.*")
            self.model = load_model(self.model_id)

        # Ensure pipeline uses this repo for voice assets (mlx_audio default is prince-canuma/Kokoro-82M)
        if hasattr(self.model, "repo_id") and self.model.repo_id is None:
            self.model.repo_id = self.model_id

        if not hasattr(self.model, "generate") or not hasattr(self.model, "sample_rate"):
            raise RuntimeError(
                "Kokoro model did not load correctly (missing generate or sample_rate). "
                "Check that misaki[en], spacy, and num2words are installed."
            )
        self.sample_rate = self.model.sample_rate

    def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        on_first_chunk=None,
    ) -> Tuple[np.ndarray, int]:
        """Generate audio from text. Returns (audio_ndarray, sample_rate).

        Args:
            text: Text to convert to speech.
            voice: Voice preset. Options: af_heart, af_bella, af_nicole, af_sky,
                   am_adam, am_echo, am_liam, bf_emma, bf_isabella, bm_george, bm_lewis.
        """
        if self.model is None:
            self.load()

        if voice is None:
            voice = self.default_voice

        kwargs = {"text": text, "voice": voice, "verbose": False, "stream": False}

        import io
        import sys
        _stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            _t0 = time.perf_counter()
            results = self.model.generate(**kwargs)
            audio_chunks = []
            for result in results:
                audio_chunks.append(result.audio)
            self.last_latency_s = time.perf_counter() - _t0
        finally:
            sys.stdout = _stdout

        if len(audio_chunks) > 1:
            import mlx.core as mx
            audio = mx.concatenate(audio_chunks, axis=0)
        else:
            audio = audio_chunks[0]

        return np.array(audio), self.sample_rate

    def synthesize_to_file(
        self,
        text: str,
        output_path: Path,
        voice: Optional[str] = None,
    ) -> float:
        """Synthesize and save to file. Returns duration in seconds."""
        audio, sample_rate = self.synthesize(text, voice=voice)

        from mlx_audio.audio_io import write as audio_write
        audio_write(str(output_path), audio, sample_rate, format="mp3")

        return len(audio) / sample_rate
