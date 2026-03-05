"""Local Text-to-Speech using MLX-Audio (Qwen3-TTS or Kokoro)."""
import os
os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'

import time
import numpy as np
from pathlib import Path
from typing import Optional, Tuple


QWEN3_MODEL_ID = "mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit"
QWEN3_VOICES = ["serena", "vivian", "uncle_fu", "ryan", "aiden", "ono_anna", "sohee", "eric", "dylan"]
QWEN3_DEFAULT_VOICE = "ryan"

KOKORO_MODEL_ID = "mlx-community/Kokoro-82M-bf16"
KOKORO_VOICES = ["af_heart", "af_bella", "af_nicole", "af_sky", "am_adam", "am_echo", "am_liam", "bf_emma", "bf_isabella", "bm_george", "bm_lewis"]
KOKORO_DEFAULT_VOICE = "af_heart"


class MlxTts:
    """Wrapper around mlx_audio TTS models (Qwen3-TTS or Kokoro).

    Select backend at init time: backend="kokoro" (default) or backend="qwen3".
    Kokoro is ~7x smaller (82M vs 600M params) and faster, but does not support
    ref_audio voice cloning. Qwen3 supports voice cloning via ref_audio.
    """

    def __init__(self, backend: str = "kokoro"):
        """Initialize the TTS wrapper.

        Args:
            backend: "kokoro" (default, fast 82M params) or "qwen3" (supports voice cloning).
        """
        if backend not in ("qwen3", "kokoro"):
            raise ValueError(f"Unknown TTS backend '{backend}'. Choose 'qwen3' or 'kokoro'.")

        self.backend = backend
        if backend == "kokoro":
            self.model_id = KOKORO_MODEL_ID
            self.default_voice = KOKORO_DEFAULT_VOICE
        else:
            self.model_id = QWEN3_MODEL_ID
            self.default_voice = QWEN3_DEFAULT_VOICE

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

        self.sample_rate = self.model.sample_rate

    def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        ref_audio: Optional[str] = None
    ) -> Tuple[np.ndarray, int]:
        """Generate audio from text. Returns (audio_ndarray, sample_rate).

        Args:
            text: Text to convert to speech.
            voice: Voice preset (default depends on backend).
                  qwen3 voices:  serena, vivian, uncle_fu, ryan, aiden, ono_anna, sohee, eric, dylan
                  kokoro voices: af_heart, af_bella, af_nicole, af_sky, am_adam, am_echo,
                                 am_liam, bf_emma, bf_isabella, bm_george, bm_lewis
            ref_audio: Path to reference audio for voice cloning (qwen3 only; ignored for kokoro).
        """
        if self.model is None:
            self.load()

        if voice is None:
            voice = self.default_voice

        kwargs = {"text": text, "verbose": False, "stream": False}

        if ref_audio and self.backend == "kokoro":
            import warnings
            warnings.warn("ref_audio voice cloning is not supported with the kokoro backend; ignoring --voice-sample.")
            ref_audio = None

        if ref_audio:
            kwargs["ref_audio"] = ref_audio
        else:
            kwargs["voice"] = voice

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
        ref_audio: Optional[str] = None
    ) -> float:
        """Synthesize and save to file. Returns duration in seconds."""
        audio, sample_rate = self.synthesize(text, voice=voice, ref_audio=ref_audio)

        from mlx_audio.audio_io import write as audio_write
        audio_write(str(output_path), audio, sample_rate, format="mp3")

        return len(audio) / sample_rate
