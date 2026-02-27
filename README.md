# Improv

Real-time voice-to-voice theatrical improv partner using local MLX models (Apple Silicon only).

## Features

- Voice-to-voice conversation loop with WebRTC VAD turn detection
- Theatrical improv principles (yes-and, realistic scenarios only)
- All local models — no API calls, no internet required after setup
- Human or AI can start the scene
- Two TTS backends: Kokoro 82M (default, fast) or Qwen3-TTS (voice cloning)

## Requirements

- Apple Silicon Mac (M1/M2/M3/M4)
- Python 3.10+
- 16GB+ unified memory recommended

## Installation

### 1. System dependency (required for Kokoro TTS)

```bash
brew install espeak-ng
```

### 2. Python dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. LLM via LM Studio

Download the LLM model in LM Studio before running:

- Model: `lmstudio-community/Qwen3-4B-Instruct-2507-MLX-4bit`
- Expected path: `~/.lmstudio/models/lmstudio-community/Qwen3-4B-Instruct-2507-MLX-4bit`

## First Run

On first run, TTS and STT models are automatically downloaded from HuggingFace:

| Model | Size |
|-------|------|
| Kokoro-82M-bf16 (TTS) | ~355 MB |
| parakeet-tdt_ctc-110m (STT) | ~437 MB |

Total ~800 MB, downloaded once and cached locally.

## Usage

```bash
# Default: Kokoro TTS, human starts the scene
python improv.py

# AI sets the scene on the first turn
python improv.py --ai-starts

# Choose a Kokoro voice
python improv.py -v am_adam

# Switch to Qwen3-TTS (supports voice cloning)
python improv.py --tts qwen3
python improv.py --tts qwen3 -v ryan
python improv.py --tts qwen3 --voice-sample my_voice.wav

# Combine options
python improv.py --tts qwen3 --ai-starts -v serena
```

## Voice Presets

**Kokoro (default TTS):**

| Code | Description |
|------|-------------|
| `af_heart` | American Female (default) |
| `af_bella` | American Female |
| `af_nicole` | American Female |
| `af_sky` | American Female |
| `am_adam` | American Male |
| `am_echo` | American Male |
| `am_liam` | American Male |
| `bf_emma` | British Female |
| `bf_isabella` | British Female |
| `bm_george` | British Male |
| `bm_lewis` | British Male |

**Qwen3-TTS (`--tts qwen3`):**

`serena` `vivian` `uncle_fu` `ryan` `aiden` `ono_anna` `sohee` `eric` `dylan`

## Models

| Component | Model | Size | Why |
|-----------|-------|------|-----|
| LLM | Qwen3-4B-Instruct-2507-MLX-4bit | 2.1 GB | MLX-optimized port of Qwen3-4B for Apple Silicon |
| TTS (default) | mlx-community/Kokoro-82M-bf16 | 355 MB | Faster than Qwen3-TTS; 82M params vs 600M |
| TTS (optional) | mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit | ~600 MB | Higher quality, supports voice cloning |
| STT | mlx-community/parakeet-tdt_ctc-110m | 437 MB | Lightweight variant of NVIDIA Parakeet 0.6B (2.3GB); no fixed 30s window (Whisper's bottleneck) |

## Recording behavior

Uses WebRTC VAD (Voice Activity Detection) for turn detection:

| Setting | Value | Config param | Notes |
|---------|-------|--------------|-------|
| VAD mode | 1 (balanced) | `Vad(1)` in `audio_io.py:23` | Range 0–3; higher = more aggressive silence detection |
| Frame size | 30ms | fixed | Required by WebRTC VAD at 16kHz |
| Silence threshold | **0.8s** | `silence_duration` in `audio_io.py:27` | Stops recording after this much continuous silence |
| Max duration | **10s** | `max_duration` in `audio_io.py:28` | Hard cap per turn regardless of speech |

The silence clock only starts after you begin speaking — background noise before your turn doesn't trigger early cutoff.

## Known Issues

- **VAD cuts off mid-sentence** — the 0.8s silence threshold may stop recording if you pause between words; lower `silence_duration` in `audio_io.py:27` if this is frequent
- **Parakeet 110M accuracy** — the 110M model trades accuracy for speed vs the full 0.6B (2.3GB); it occasionally misrecognises uncommon words
- **Voice cloning ignored with Kokoro** — `--voice-sample` is silently skipped when using the default Kokoro backend; use `--tts qwen3 --voice-sample` instead
- **AI occasionally breaks scene rules** — the LLM may introduce fantasy elements or repeat words despite prompt constraints

## Exit

Say **"end scene"**, **"and scene"**, or press Ctrl+C.
