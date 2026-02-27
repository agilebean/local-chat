# Improv

Real-time voice-to-voice theatrical improv partner using local MLX models (Apple Silicon only).

## Features

- Voice-to-voice conversation loop
- Theatrical improv principles (yes-and, realistic scenarios)
- All local models — no API calls
- WebRTC VAD for turn detection
- 9 voice presets + voice cloning

## Requirements

- Apple Silicon Mac (M1/M2/M3/M4)
- Python 3.10+
- 16GB+ unified memory recommended

## Installation

```bash
# Create and activate a virtual environment (Python 3.10+)
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

## Prerequisite: LM Studio Model

Download Qwen3-4B-Instruct to LM Studio before running:

- Model: `lmstudio-community/Qwen3-4B-Instruct-2507-MLX-4bit`
- Expected path: `~/.lmstudio/models/lmstudio-community/Qwen3-4B-Instruct-2507-MLX-4bit`

## Usage

```bash
# Default voice
python improv.py

# Specific voice preset
python improv.py -v ryan

# Voice cloning from audio sample
python improv.py --voice-sample my_voice.wav
```

## Voice Presets

`serena` `vivian` `uncle_fu` `ryan` `aiden` `ono_anna` `sohee` `eric` `dylan`

## Models

| Component | Model |
|-----------|-------|
| LLM | Qwen3-4B-Instruct (local, from LM Studio) |
| TTS | Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit (HuggingFace) |
| STT | mlx-community/whisper-tiny (HuggingFace) |

## First Run

On first run, the TTS and STT models are automatically downloaded from HuggingFace (~500MB total). This takes a few minutes and only happens once. Subsequent runs load from the local cache.

## Exit

Say "end scene" or press Ctrl+C.

## Known Issues

- Whisper-tiny occasionally misses words or cuts off the last word
- WebRTC VAD (0.8s silence threshold) may cut off mid-sentence if you pause too long
- AI may occasionally ignore the realistic-scenarios constraint
