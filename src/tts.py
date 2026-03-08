"""Local Text-to-Speech using MLX-Audio (Kokoro) or NeuTTS Nano."""
import os
os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'

import time
import numpy as np
from pathlib import Path
from typing import Optional, Tuple


KOKORO_MODEL_ID = "mlx-community/Kokoro-82M-bf16"
KOKORO_VOICES = ["af_heart", "af_bella", "af_nicole", "af_sky", "am_adam", "am_echo", "am_liam", "bf_emma", "bf_isabella", "bm_george", "bm_lewis"]
KOKORO_DEFAULT_VOICE = "af_heart"

NEUTTS_VOICES = ["jo", "dave", "greta", "juliette", "mateo"]
NEUTTS_DEFAULT_VOICE = "jo"
_NEUTTS_SAMPLES_DIR = Path(__file__).parent.parent / "samples"


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


class NeuTtsTts:
    """Wrapper around NeuTTS Nano (GGUF/llama.cpp) TTS model.

    Uses pre-encoded .pt reference codes from samples/ for named voice presets.
    Streams audio in real-time via sounddevice as tokens are generated.
    """

    def __init__(self):
        self.default_voice = NEUTTS_DEFAULT_VOICE
        self.sample_rate = 24000
        self.model = None
        self.last_latency_s: float = 0.0
        self.streams_inline: bool = True  # plays audio during synthesize(); caller skips player.play()
        self._ref_cache: dict = {}  # voice -> (ref_codes, ref_text)

    def load(self):
        """Lazy-load NeuTTS GGUF model."""
        if self.model is not None:
            return

        import os, sys
        from neutts import NeuTTS
        # Suppress llama.cpp Metal init noise (bf16-not-supported lines) by
        # redirecting the C-level stderr during model construction.
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
        old_stderr_fd = os.dup(2)
        os.dup2(devnull_fd, 2)
        os.close(devnull_fd)
        try:
            self.model = NeuTTS(
                backbone_repo="neuphonic/neutts-nano-q4-gguf",
                backbone_device="cpu",
                codec_repo="neuphonic/neucodec-onnx-decoder",
                codec_device="cpu",
            )
        finally:
            os.dup2(old_stderr_fd, 2)
            os.close(old_stderr_fd)

    def _get_ref(self, voice: str) -> tuple:
        """Load pre-encoded reference codes for a named voice (cached)."""
        if voice not in self._ref_cache:
            pt_path = _NEUTTS_SAMPLES_DIR / f"{voice}.pt"
            txt_path = _NEUTTS_SAMPLES_DIR / f"{voice}.txt"
            if not pt_path.exists():
                raise ValueError(
                    f"NeuTTS voice '{voice}' not found at {pt_path}. "
                    f"Available: {NEUTTS_VOICES}"
                )
            import torch
            ref_codes = torch.load(str(pt_path), weights_only=True)
            ref_text = txt_path.read_text().strip() if txt_path.exists() else ""
            self._ref_cache[voice] = (ref_codes, ref_text)
        return self._ref_cache[voice]

    def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        on_first_chunk=None,
    ) -> Tuple[np.ndarray, int]:
        """Stream audio to speakers in real-time and return combined waveform."""
        if self.model is None:
            self.load()

        if voice is None:
            voice = self.default_voice

        ref_codes, ref_text = self._get_ref(voice)

        import sounddevice as sd
        import queue as _queue
        from collections import deque

        audio_q = _queue.SimpleQueue()
        pending = deque()  # partially consumed chunk
        chunks = []

        def callback(outdata, frames, time_info, status):
            out = np.zeros(frames, dtype=np.float32)
            pos = 0
            while pos < frames:
                if not pending:
                    try:
                        pending.append(audio_q.get_nowait())
                    except _queue.Empty:
                        break  # underrun — fill rest with silence
                seg = pending[0]
                n = min(len(seg), frames - pos)
                out[pos:pos + n] = seg[:n]
                pos += n
                if n < len(seg):
                    pending[0] = seg[n:]
                else:
                    pending.popleft()
            outdata[:, 0] = out

        _t0 = time.perf_counter()
        stream = sd.OutputStream(
            samplerate=self.sample_rate, channels=1, dtype="float32",
            blocksize=1024, callback=callback,
        )
        stream.start()

        first_chunk = True
        for chunk in self.model.infer_stream(text, ref_codes, ref_text):
            chunk = np.asarray(chunk, dtype=np.float32)
            if first_chunk:
                self.last_latency_s = time.perf_counter() - _t0
                if on_first_chunk:
                    on_first_chunk(self.last_latency_s)
                first_chunk = False
            audio_q.put(chunk)
            chunks.append(chunk)

        # Wait for Python-side buffers to drain into PortAudio, then
        # stream.stop() (Pa_StopStream) waits for PortAudio to finish playing.
        while not audio_q.empty() or pending:
            time.sleep(0.005)
        stream.stop()
        stream.close()

        return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32), self.sample_rate

    def synthesize_to_file(
        self,
        text: str,
        output_path: Path,
        voice: Optional[str] = None,
    ) -> float:
        """Synthesize and save to file. Returns duration in seconds."""
        audio, sample_rate = self.synthesize(text, voice=voice)

        import soundfile as sf
        sf.write(str(output_path), audio, sample_rate)

        return len(audio) / sample_rate
