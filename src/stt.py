"""Local Speech-to-Text using MLX Whisper."""
import os
os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'

import numpy as np
from typing import Optional


class MlxStt:
    """Wrapper around mlx-whisper for speech recognition.

    Uses Apple Silicon optimized Whisper models for fast, local STT.
    """

    DEFAULT_MODEL = "mlx-community/whisper-tiny"
    # whisper-tiny is fastest for real-time use
    # This is the only model confirmed to work in mlx-community

    def __init__(self, model_name: Optional[str] = None):
        """Initialize the STT wrapper.

        Args:
            model_name: HuggingFace model ID or local path.
                       Defaults to whisper-tiny (fastest available).
        """
        self.model_name = model_name or self.DEFAULT_MODEL

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe audio numpy array to text.

        Args:
            audio: Audio as float32 numpy array (mono).
                  Whisper expects 16kHz, but will resample if needed.
            sample_rate: Sample rate of the audio (default: 16000 Hz).

        Returns:
            Transcribed text string.
        """
        import mlx_whisper

        # mlx_whisper.transcribe() accepts numpy arrays directly
        # It also handles resampling internally if needed
        result = mlx_whisper.transcribe(
            audio,
            path_or_hf_repo=self.model_name,
            language="en"
        )

        return result["text"].strip()
