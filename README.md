# Improv

Real-time voice-to-voice theatrical improv partner using local MLX models (Apple Silicon only).

## Features

- Voice-to-voice conversation loop with WebRTC VAD turn detection
- Theatrical improv principles (yes-and, realistic scenarios only)
- All local models — no API calls, no internet required after setup
- Human or AI can start the scene
- Kokoro 82M TTS (fast, preset voices)

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

If you see a spacy/pydantic error (e.g. `ConfigError: unable to infer type for attribute "REGEX"`) on Python 3.14, use a 3.12 env: `mamba create -n improv python=3.12 -y` then `mamba activate improv` and reinstall.

**Smaller env:** `misaki[en]` pulls in spacy-curated-transformers and PyTorch (~400 MB). Kokoro uses `trf=False` and does not need them. After installing with `pip install -r requirements.txt`, you can remove them to save space:

```bash
mamba activate improv
pip uninstall -y torch spacy-curated-transformers curated-transformers
```

### 3. LLM via LM Studio

Download the LLM model in LM Studio before running:

- Model: `lmstudio-community/Qwen3-4B-Instruct-2507-MLX-4bit`
- Expected path: `~/.lmstudio/models/lmstudio-community/Qwen3-4B-Instruct-2507-MLX-4bit`

## First Run

On first run, models are automatically downloaded from HuggingFace:

| Model | Size | When |
|-------|------|------|
| Kokoro-82M-bf16 (TTS) | ~355 MB | always |
| parakeet-tdt_ctc-110m (STT) | ~437 MB | always |

## Usage

```bash
# Default: human starts the scene (Kokoro TTS)
python improv.py

# AI sets the scene on the first turn
python improv.py --ai-starts

# Choose a Kokoro voice
python improv.py -v am_adam

# Different LLM size
python improv.py --llm 4b

# Combine options
python improv.py --ai-starts -v am_adam --llm 4b
```

## CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `-v / --voice` | `af_heart` | Kokoro voice preset (see below). |
| `--llm` | `2b` | LLM size: `0.8b`, `2b`, `4b`, `qwen3` |
| `--ai-starts` | off | AI sets the scene on the first turn |

## Voice Presets (Kokoro)

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

## Models

| Component | Model | Size | Why |
|-----------|-------|------|-----|
| LLM (`--llm 0.8b`) | mlx-community/Qwen3.5-0.8B-MLX-4bit | 622 MB | Fastest option |
| LLM (`--llm 2b`, default) | mlx-community/Qwen3.5-2B-MLX-4bit | 1.6 GB | Good balance of speed and quality |
| LLM (`--llm 4b`) | mlx-community/Qwen3.5-4B-MLX-4bit | 2.9 GB | Highest quality Qwen3.5 variant |
| LLM (`--llm qwen3`) | lmstudio-community/Qwen3-4B-Instruct-2507-MLX-4bit | 2.1 GB | MLX-optimized Qwen3-4B for Apple Silicon |
| TTS (Kokoro) | mlx-community/Kokoro-82M-bf16 | 345 MB | 82M params, preset voices, fast MLX inference |
| STT | mlx-community/parakeet-tdt_ctc-110m | 437 MB | Lightweight NVIDIA Parakeet variant; no fixed 30s window (Whisper's bottleneck) |

> **Note (LLM):** The Qwen3.5 `0.8b`/`2b`/`4b` weight files are multimodal checkpoints. Only the language model portion is used — vision tower weights are silently skipped at load time via `strict=False`.

## Recording behavior

Uses WebRTC VAD (Voice Activity Detection) for turn detection:

| Setting | Value | Config param | Notes |
|---------|-------|--------------|-------|
| VAD mode | 2 (moderately aggressive) | `Vad(2)` in `audio_io.py:23` | Range 0–3; higher = more aggressive silence detection |
| Frame size | 30ms | fixed | Required by WebRTC VAD at 16kHz |
| Silence threshold | **0.8s** | `silence_duration` in `audio_io.py:27` | Stops recording after this much continuous silence |
| Max duration | **30s** | `max_duration` in `audio_io.py:28` | Hard cap per turn regardless of speech |

The silence clock only starts after you begin speaking — background noise before your turn doesn't trigger early cutoff.

## Known Issues

- **VAD cuts off mid-sentence** — the 0.8s silence threshold may stop recording if you pause between words; lower `silence_duration` in `audio_io.py:27` if this is frequent
- **Parakeet 110M accuracy** — the 110M model trades accuracy for speed vs the full 0.6B (2.3GB); it occasionally misrecognises uncommon words
- **AI occasionally breaks scene rules** — the LLM may introduce fantasy elements or repeat words despite prompt constraints

## Exit

Say **"end scene"**, **"and scene"**, or press Ctrl+C.

## YouTube helper (optional)

The `youtube/youtube_to_speech.py` helper in this repo is a thin wrapper that calls the original\n`talk_to_tone` project in a separate `talk_to_tone` environment. A few caveats:\n\n- **Transcripts and VPNs**: If you see an error like:\n+\n+  > Could not retrieve a transcript for the video ... YouTube is blocking requests from your IP\n+\n+  then YouTube is rejecting `youtube-transcript-api` requests from your IP (often due to a VPN or\n+  unusual traffic). Disable your VPN or switch networks, or pass a local `.txt` / `.md` transcript\n+  file instead of a YouTube URL.\n+- **Kokoro errors in YouTube helper**: If Kokoro works in improv (`improv.py`) but the YouTube\n+  helper prints `Model type kokoro not supported for tts`, that error is coming from the\n+  **`talk_to_tone` env**, which may have an older `mlx-audio` without Kokoro support. Fix it with:\n+\n+  ```bash\n+  mamba activate talk_to_tone\n+  pip install -U \"mlx-audio>=0.4.1\"\n+  ```\n+
