"""Local Speech-to-Text using Parakeet TDT (MLX)."""
import os
os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'

import tempfile
import numpy as np
import soundfile as sf
from typing import Optional


class MlxStt:
    """Wrapper around parakeet-mlx for speech recognition.

    Uses Parakeet TDT (Transducer architecture) — no fixed 30s window,
    much lower latency than Whisper for short conversational speech.
    """

    DEFAULT_MODEL = "mlx-community/parakeet-tdt_ctc-110m"

    def __init__(self, model_name: Optional[str] = None):
        """Initialize the STT wrapper.

        Args:
            model_name: HuggingFace model ID or local path.
        """
        self.model_name = model_name or self.DEFAULT_MODEL
        self._model = None

    def load(self):
        """Pre-load the model into memory."""
        from parakeet_mlx import from_pretrained

        # Re-enable progress bars for this download — first run fetches ~1.2GB
        # and suppressing output makes it look like a hang.
        prev = os.environ.pop('HF_HUB_DISABLE_PROGRESS_BARS', None)
        try:
            self._model = from_pretrained(self.model_name)
        finally:
            if prev is not None:
                os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = prev

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe audio numpy array to text.

        Args:
            audio: Audio as float32 numpy array (mono, 16kHz).
            sample_rate: Sample rate of the audio (default: 16000 Hz).

        Returns:
            Transcribed text string.
        """
        if self._model is None:
            self.load()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name

        try:
            sf.write(tmp_path, audio, sample_rate)
            result = self._model.transcribe(tmp_path)
            return result.text.strip()
        finally:
            os.unlink(tmp_path)
