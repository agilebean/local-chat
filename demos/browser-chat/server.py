"""Browser-chat backend.

Serves the static demo files AND exposes two extra endpoints:

    GET  /health   -> JSON capability probe
                      { "kokoro_available": bool, "voices": [...],
                        "default_voice": str, "error": str|null }

    POST /tts      -> WAV audio bytes
                      Body: { "text": "...", "voice": "af_heart" }

Kokoro is loaded lazily on the first /tts request, so the server still
runs (static files + /health) when MLX/mlx_audio aren't installed — the
browser detects this via /health and grays out the Kokoro option.
"""
import io
import json
import os
import sys
import wave
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMPROV_ROOT = HERE.parent.parent
sys.path.insert(0, str(IMPROV_ROOT))

# Voice list is just constants — safe to import even without MLX.
try:
    from src.tts import KOKORO_VOICES, KOKORO_DEFAULT_VOICE, KOKORO_VOICE_DESCRIPTIONS
except Exception:
    KOKORO_VOICES = ["af_heart"]
    KOKORO_DEFAULT_VOICE = "af_heart"
    KOKORO_VOICE_DESCRIPTIONS = {}


_tts = None
_tts_error: str | None = None


def _ensure_tts():
    """Lazy-load Kokoro on first request. Caches success and failure."""
    global _tts, _tts_error
    if _tts is not None:
        return _tts
    if _tts_error is not None:
        return None
    try:
        from src.tts import MlxTts
        t = MlxTts()
        t.load()
        _tts = t
        print(f"[tts] Kokoro loaded (sample_rate={t.sample_rate})")
        return t
    except Exception as e:
        _tts_error = f"{type(e).__name__}: {e}"
        print(f"[tts] Kokoro unavailable: {_tts_error}")
        return None


def _wav_bytes(audio, sample_rate: int) -> bytes:
    """Encode float32 mono audio in [-1, 1] as 16-bit PCM WAV."""
    import numpy as np
    audio = np.clip(np.asarray(audio, dtype=np.float32), -1.0, 1.0)
    pcm = (audio * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(sample_rate))
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(HERE), **kwargs)

    # localhost-only deployment: permissive CORS keeps things simple
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            return self._send_json({
                "kokoro_available": _ensure_tts() is not None,
                "voices": KOKORO_VOICES,
                "default_voice": KOKORO_DEFAULT_VOICE,
                "voice_descriptions": KOKORO_VOICE_DESCRIPTIONS,
                "error": _tts_error,
            })
        return super().do_GET()

    def do_POST(self):
        if self.path == "/tts":
            return self._handle_tts()
        self.send_error(404, "Not found")

    def _send_json(self, data, code: int = 200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _handle_tts(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            text = (payload.get("text") or "").strip()
            voice = payload.get("voice") or KOKORO_DEFAULT_VOICE

            if not text:
                return self._send_json({"error": "empty text"}, code=400)
            if voice not in KOKORO_VOICES:
                return self._send_json(
                    {"error": f"unknown voice '{voice}'", "voices": KOKORO_VOICES},
                    code=400,
                )

            tts = _ensure_tts()
            if tts is None:
                return self._send_json(
                    {"error": _tts_error or "Kokoro TTS unavailable"},
                    code=503,
                )

            audio, sr = tts.synthesize(text, voice=voice)
            data = _wav_bytes(audio, sr)

            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(data)))
            self._cors()
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self._send_json({"error": f"{type(e).__name__}: {e}"}, code=500)


def main():
    port = int(os.environ.get("PORT", 8000))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Browser Chat backend on http://localhost:{port}")
    print(f"Static dir: {HERE}")
    print("Kokoro TTS will load lazily on first /tts request.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down")


if __name__ == "__main__":
    main()
