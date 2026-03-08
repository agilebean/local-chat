# Improv

Real-time voice-to-voice theatrical improv partner using local MLX models (Apple Silicon only).

## Features

- Voice-to-voice conversation loop with WebRTC VAD turn detection
- Theatrical improv principles (yes-and, realistic scenarios only)
- All local models — no API calls, no internet required after setup
- Human or AI can start the scene
- Two TTS backends: Kokoro 82M (fast, preset voices) or NeuTTS Nano (120M, voice cloning, real-time streaming)

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

### 3. NeuTTS backend (optional — only needed for `--tts neutts-nano`)

Install `llama-cpp-python` with Metal acceleration (Apple Silicon):

```bash
CMAKE_ARGS="-DGGML_METAL=on" pip install llama-cpp-python
```

Then install neutts:

```bash
pip install "neutts[llama]"
```

### 4. LLM via LM Studio

Download the LLM model in LM Studio before running:

- Model: `lmstudio-community/Qwen3-4B-Instruct-2507-MLX-4bit`
- Expected path: `~/.lmstudio/models/lmstudio-community/Qwen3-4B-Instruct-2507-MLX-4bit`

## First Run

On first run, models are automatically downloaded from HuggingFace:

| Model | Size | When |
|-------|------|------|
| Kokoro-82M-bf16 (TTS) | ~355 MB | always |
| parakeet-tdt_ctc-110m (STT) | ~437 MB | always |
| neutts-nano-q4-gguf (TTS backbone) | ~500 MB | `--tts neutts-nano` only |
| neucodec-onnx-decoder (TTS codec) | ~50 MB | `--tts neutts-nano` only |

## Usage

```bash
# Default: human starts the scene (Kokoro TTS)
python improv.py

# AI sets the scene on the first turn
python improv.py --ai-starts

# Choose a Kokoro voice
python improv.py -v am_adam

# Use NeuTTS Nano — voice name auto-selects backend
python improv.py -v jo
python improv.py -v dave

# Explicit backend + voice
python improv.py --tts neutts-nano -v jo

# Different LLM size
python improv.py --llm 4b

# Combine options
python improv.py --ai-starts -v am_adam --llm 4b
```

## CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--tts` | `kokoro` | TTS backend: `kokoro` or `neutts-nano` |
| `-v / --voice` | backend default | Voice preset (see below). NeuTTS voice names auto-select `--tts neutts-nano`. |
| `--llm` | `2b` | LLM size: `0.8b`, `2b`, `4b`, `qwen3` |
| `--ai-starts` | off | AI sets the scene on the first turn |

## Voice Presets

### Kokoro (`--tts kokoro`, default)

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

### NeuTTS Nano (`--tts neutts-nano`)

| Code | Language | Gender |
|------|----------|--------|
| `jo` | English | Female (default) |
| `dave` | English | Male |
| `greta` | German | Female |
| `juliette` | French | Female |
| `mateo` | Spanish | Male |

Pre-encoded reference codes are stored in `samples/`. Passing any NeuTTS voice name auto-selects `--tts neutts-nano`, so `-v jo` is sufficient.

## Models

| Component | Model | Size | Why |
|-----------|-------|------|-----|
| LLM (`--llm 0.8b`) | mlx-community/Qwen3.5-0.8B-MLX-4bit | 622 MB | Fastest option |
| LLM (`--llm 2b`, default) | mlx-community/Qwen3.5-2B-MLX-4bit | 1.6 GB | Good balance of speed and quality |
| LLM (`--llm 4b`) | mlx-community/Qwen3.5-4B-MLX-4bit | 2.9 GB | Highest quality Qwen3.5 variant |
| LLM (`--llm qwen3`) | lmstudio-community/Qwen3-4B-Instruct-2507-MLX-4bit | 2.1 GB | MLX-optimized Qwen3-4B for Apple Silicon |
| TTS (`--tts kokoro`, default) | mlx-community/Kokoro-82M-bf16 | 345 MB | 82M params, preset voices, fast MLX inference |
| TTS (`--tts neutts-nano`) | neuphonic/neutts-nano-q4-gguf + neuphonic/neucodec-onnx-decoder | ~550 MB | 120M active params (229M total), voice cloning, real-time streaming via llama.cpp + ONNX codec |
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
- **NeuTTS gaps during slow generation** — if the model generates slower than real-time on your hardware, brief silence gaps may appear between audio chunks

## Removing NeuTTS

NeuTTS is optional and self-contained. To remove it cleanly:

**1. Delete the sample reference files:**
```bash
rm -rf samples/
```

**2. Uninstall the packages:**
```bash
pip uninstall neutts onnxruntime llama-cpp-python
```

**3. Remove from `requirements.txt`** — delete these lines:
```
neutts>=0.1.0
onnxruntime>=1.20.0
```

**4. Remove from `src/tts.py`** — delete:
- `NEUTTS_VOICES`, `NEUTTS_DEFAULT_VOICE`, `_NEUTTS_SAMPLES_DIR` constants
- The entire `NeuTtsTts` class

**5. Remove from `src/improv_loop.py`** — delete:
- `NeuTtsTts` from the import on line 26
- The `else NeuTtsTts()` branch in `__init__`
- The `tts_label` neutts-nano branch in `load_models()`

**6. Remove from `improv.py`** — delete:
- `from src.tts import NEUTTS_VOICES`
- The `--tts` argument
- The auto-detect block (`if args.voice in NEUTTS_VOICES`)
- The `tts_backend` arg from `ImprovSession()`

**7. Remove from `README.md`** — delete:
- Installation step 3 (NeuTTS backend)
- First Run table rows for neutts-nano and neucodec
- Usage examples with `-v jo` / `-v dave`
- `--tts` row from CLI Options table
- NeuTTS Nano voice presets section
- NeuTTS row from Models table
- NeuTTS Known Issue
- This entire "Removing NeuTTS" section

## Exit

Say **"end scene"**, **"and scene"**, or press Ctrl+C.
