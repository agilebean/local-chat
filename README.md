# local-chat

Local-first AI chat for Apple Silicon — four ways to converse with on-device
models, sharing the same MLX runtime and Kokoro 82M TTS:

- talk back and forth with an improv partner ([Improv](#improv))
- chat with a tiny LLM in your browser ([Browser Chat](#browser-chat))
- have a video summarized to you, with optional music
  ([YouTube to Speech](#youtube-to-speech))
- prompt-chat with an audio model to compose music ([Music Gen](#music-gen))

**Apps:**
[Improv](#improv) · [Browser Chat](#browser-chat) · [YouTube to Speech](#youtube-to-speech) · [Music Gen](#music-gen)

**Reference:**
[Requirements](#requirements) · [Installation](#installation) · [Voice Presets](#voice-presets-kokoro) · [Models](#models) · [Recording behavior](#recording-behavior) · [Known Issues](#known-issues)

---

## Apps

### Improv

[`improv.py`](improv.py) — voice-to-voice theatrical AI improv partner.

- Real-time conversation loop with WebRTC VAD turn detection
- STT (Parakeet) → LLM (Qwen3.5 / Qwen3) → TTS (Kokoro 82M)
- Human or AI sets the opening scene; "yes-and" prompt enforces realism

```bash
local                                                     # alias: activates improv mamba env, cd into repo
python improv.py                                          # human starts the scene
python improv.py --ai-starts --voice am_adam --llm 4b     # full options
```

| Flag | Default | Description |
|------|---------|-------------|
| `--voice` | `af_heart` | Kokoro voice preset — see [Voice Presets](#voice-presets-kokoro) |
| `--llm` | `2b` | LLM size: `0.8b`, `2b`, `4b` (Qwen3.5), or `qwen3` (Qwen3-4B-Instruct) |
| `--ai-starts` | off | AI sets the scene on the first turn |

> **For `--llm qwen3` only:** download in LM Studio first.
> Repo `lmstudio-community/Qwen3-4B-Instruct-2507-MLX-4bit` →
> `~/.lmstudio/models/lmstudio-community/Qwen3-4B-Instruct-2507-MLX-4bit`.
> The other variants auto-download from HuggingFace on first run.

Exit a scene by saying **"end scene"**, **"and scene"**, or pressing Ctrl+C.

---

### Browser Chat

[`demos/browser-chat/`](demos/browser-chat/) — local STT, TTS, and LLM running in the browser.

- Zero-install for end users — open a URL, no Python or build step
- Tiny local LLM (Qwen2.5-0.5B / SmolLM2-360M / Qwen2.5-1.5B), ~350 MB cached once
- WebLLM on WebGPU for inference; optional Kokoro TTS via the same Python backend
- Requires Chrome 113+, Edge, or Safari 26+ (WebGPU)

```bash
browserchat            # alias: activates improv env, runs ./start.command
                       # which starts server.py and opens http://localhost:8000
```

Without the `improv` env active, `python3 server.py` still serves the page;
TTS falls back to the browser's native `SpeechSynthesis`.

---

### YouTube to Speech

[`youtube/youtube_to_speech.py`](youtube/youtube_to_speech.py) — turn any YouTube video into spoken audio, optionally with music. Three layered modes share one CLI:

- **Speech only** (default) — summarize transcript → Kokoro reads it aloud.
- **Speech + background music** (`--genre` / `--music-prompt`) — MLX MusicGen
  produces a short backing clip, ffmpeg loops it to cover the speech and
  mixes them (music @ 0.3, speech @ 0.55) → `speech_on_music.mp3`.
- **Full vocal song** (`--song`) — SunoAPI.org generates a ~2 min song whose
  lyrics are about the video topic. Replaces the old `talk_to_tone --song`
  flow; everything runs from this one script now.

#### Mode 1 — Speech only

```bash
local                                                        # alias: activates improv mamba env, cd into repo
python youtube/youtube_to_speech.py "YOUTUBE_URL_OR_PATH"
python youtube/youtube_to_speech.py URL --voice am_adam --words 80
```

Outputs `output/<slug>/{summary.txt, speech.mp3}`.

#### Mode 2 — Speech + background music

```bash
# Preset genre (style prompt baked in)
python youtube/youtube_to_speech.py URL --genre jazz

# Custom MLX prompt + longer source clip before looping
python youtube/youtube_to_speech.py URL \
    --music-prompt "lo-fi piano with vinyl crackle" --music-seconds 10
```

Adds `music.mp3` (the looped backing) and the merged `speech_on_music.mp3`
to the output folder. Music backend defaults to local MLX MusicGen; pass
`--provider suno_org` to use Suno instead (vocals still off — backgrounds
are forced instrumental).

#### Mode 3 — Full vocal song (Suno)

Set `SUNO_ORG_KEY` once (key from [sunoapi.org](https://sunoapi.org)):

```bash
echo "SUNO_ORG_KEY=sk_..." >> .env        # repo-local, gitignored
# or: export SUNO_ORG_KEY=sk_...           # current shell only
```

```bash
python youtube/youtube_to_speech.py URL --song
python youtube/youtube_to_speech.py URL --song --genre taylorswift --song-seconds 90
```

The summary becomes the song topic (`"A {genre|pop} song about: {summary}"`,
truncated to 200 chars). Output: `output/<slug>/{summary.txt, song.mp3}`
(no speech or background-music files in this mode).

> **Why a separate cleanup pass for `--song`:** YouTube transcripts are
> noisy and small Qwen models occasionally echo the prompt or wrap the
> answer in meta-commentary. For Kokoro speech this is fine; for Suno
> lyrics it produces unusable input. The robust path (`extract_summary` +
> retries + sentence/word truncation, salvaged from talk_to_tone) is
> therefore gated to `--song` only.

#### All flags

| Flag | Default | Description |
|---|---|---|
| `--voice` / `-v` | `af_heart` | Kokoro voice — see [Voice Presets](#voice-presets-kokoro) |
| `--words` / `-w` | `50` | Target word count for the summary |
| `--genre` / `-g` | — | Preset style: `romantic`, `taylorswift`, `jazz`, `drumbass`. In `--song` mode it sets the song style. |
| `--music-prompt` | — | Custom MusicGen prompt (overrides `--genre`, background-music mode only) |
| `--music-seconds` | `7` | Length of the generated backing clip; looped to cover the speech |
| `--provider` / `-p` | `mlx` | Music backend: `mlx` (local) or `suno_org` (remote, needs `SUNO_ORG_KEY`). `--song` forces `suno_org`. |
| `--song` | off | Generate a full vocal song instead of speech |
| `--song-seconds` | `120` | Target song length in seconds |

---

### Music Gen

[`musicgen.py`](musicgen.py) — generate instrumental music from a text prompt with MLX MusicGen.

- Local Apple Silicon inference via the vendored
  [`ml-explore/mlx-examples`](https://github.com/ml-explore/mlx-examples)
  MusicGen package in [`src/music/musicgen/`](src/music/musicgen/) — verified
  working with MLX 0.31 / transformers 5.3 / torch 2.11.
- Pluggable backend behind a small factory: `mlx` local, or remote
  `suno` / `suno_org` via API key (see [`src/music/factory.py`](src/music/factory.py)).
- Used directly here, and as the music engine inside
  [YouTube to Speech](#youtube-to-speech) when `--genre` / `--music-prompt`
  is set.

```bash
musicgen "lo-fi hip hop with vinyl crackle" -d 15         # alias: activates improv mamba env, cd into repo, runs musicgen.py
python musicgen.py "calm piano" -d 10 -m small -o output/calm.wav
```

| Flag | Default | Description |
|------|---------|-------------|
| `-d / --duration` | `10` | Length in seconds |
| `-m / --model` | `small` | MusicGen size: `small`, `medium`, `large` |
| `-o / --output` | `output/music.wav` | Output `.wav` path |

> **Pipelining with YouTube to Speech.** No manual chaining needed — the
> YouTube CLI already triggers MusicGen as a single command:
> `--genre` / `--music-prompt` for instrumental backing under speech, or
> `--song` for a full vocal song. See [YouTube to Speech](#youtube-to-speech).

---

## Shared Features

- **All local** — no API calls, no internet required after first run
  (except [Music Gen](#music-gen) and [YouTube to Speech](#youtube-to-speech)
  when `--provider suno_org` is selected)
- **Apple Silicon MLX acceleration** — fast on-device inference on M-series GPUs
- **Kokoro 82M TTS** — preset voices, real-time on-device synthesis (always-on
  in Improv and YouTube to Speech; optional toggle in Browser Chat)

## Requirements

- Apple Silicon Mac (M1/M2/M3/M4)
- Python 3.12 (via mamba — see [Installation](#installation))
- 16GB+ unified memory recommended

## Installation

Generic setup shared by all four apps. App-specific extras live inside each
feature section above.

### 1. System dependency (required for Kokoro TTS)

```bash
brew install espeak-ng
```

### 2. Python environment (mamba)

```bash
mamba create -n improv python=3.12 -y
mamba activate improv
pip install -r requirements.txt
```

**Smaller env (optional, ~150 MB saved):** `misaki[en]` is the G2P
(text→phoneme) engine Kokoro uses. Its `[en]` extra also pulls
`spacy-curated-transformers` (and `curated-transformers`), which Kokoro
itself doesn't use because we run it with `trf=False`. Safe to drop:

```bash
pip uninstall -y spacy-curated-transformers curated-transformers
```

> **Don't uninstall `torch`.** It's pulled in by `misaki[en]` but you could
> remove it for Improv / Browser Chat / YouTube speech-only — except
> [Music Gen](#music-gen) needs it at runtime to read its `state_dict.bin`
> (where the MusicGen weights live).

## Voice Presets (Kokoro)

Used by Improv, YouTube to Speech, and Browser Chat (when Kokoro backend is on).

| Code | Accent / gender | Voice characteristics |
|------|-----------------|-----------------------|
| `af_heart` (default) | American Female | feminine light |
| `af_bella` | American Female | feminine dark |
| `af_nicole` | American Female | whisper, dark |
| `af_sky` | American Female | feminine US neutral |
| `am_adam` | American Male | masculine neutral, old |
| `am_echo` | American Male | masculine neutral, young |
| `am_liam` | American Male | salesy |
| `bf_emma` | British Female | feminine UK neutral, old |
| `bf_isabella` | British Female | feminine UK neutral, young |
| `bm_george` | British Male | masculine elder, approachable |
| `bm_lewis` | British Male | masculine narrator |

## Models

All models auto-download from HuggingFace on first run (except `--llm qwen3`,
which is downloaded manually via LM Studio — see [Improv](#improv)).

| Used by | Type | Model | Size | Why |
|---|---|---|---|---|
| all | TTS | mlx-community/Kokoro-82M-bf16 | 345 MB | 82M params, preset voices, fast MLX inference |
| Improv | STT | mlx-community/parakeet-tdt_ctc-110m | 437 MB | Lightweight Parakeet; no fixed 30s window (Whisper's bottleneck) |
| Improv `--llm 0.8b` | LLM | mlx-community/Qwen3.5-0.8B-MLX-4bit | 622 MB | Fastest |
| Improv `--llm 2b` (default) | LLM | mlx-community/Qwen3.5-2B-MLX-4bit | 1.6 GB | Speed/quality balance |
| Improv `--llm 4b` | LLM | mlx-community/Qwen3.5-4B-MLX-4bit | 2.9 GB | Highest-quality Qwen3.5 |
| Improv `--llm qwen3` | LLM | lmstudio-community/Qwen3-4B-Instruct-2507-MLX-4bit | 2.1 GB | MLX-optimized Qwen3-4B |
| Music `-m small` (default) | Music | facebook/musicgen-small | 600 MB | Fastest |

> **Note (MusicGen sizes):** `medium` (~2.7 GB) and `large` (~5.5 GB) are
> also accepted by `-m` for higher fidelity, but generation time scales
> roughly with model size on Apple Silicon.
>
> **Note (Qwen3.5 LLMs):** the `0.8b`/`2b`/`4b` checkpoints are multimodal
> weight files. Only the language-model portion is used — vision-tower
> weights are silently skipped at load time via `strict=False`.

## Recording behavior

Improv uses WebRTC VAD (Voice Activity Detection) for turn detection:

| Setting | Value | Config param | Notes |
|---------|-------|--------------|-------|
| VAD mode | 2 (moderately aggressive) | `Vad(2)` in `audio_io.py:23` | Range 0–3; higher = more aggressive silence detection |
| Frame size | 30 ms | fixed | Required by WebRTC VAD at 16 kHz |
| Silence threshold | **0.8 s** | `silence_duration` in `audio_io.py:27` | Stops recording after this much continuous silence |
| Max duration | **30 s** | `max_duration` in `audio_io.py:28` | Hard cap per turn regardless of speech |

The silence clock only starts after you begin speaking — background noise
before your turn doesn't trigger early cutoff.

## Known Issues

- **YouTube transcript blocked** — `Could not retrieve a transcript ...
  YouTube is blocking requests from your IP`. Usually a VPN or unusual
  traffic pattern; disable the VPN, switch networks, or pass a local
  `.txt` / `.md` transcript file to `youtube_to_speech.py` instead of a URL.
- **VAD cuts off mid-sentence** — the 0.8 s silence threshold may stop
  recording if you pause between words; lower `silence_duration` in
  `audio_io.py:27` if this is frequent.
- **Parakeet 110M accuracy** — the 110M model trades accuracy for speed vs
  the full 0.6B (2.3 GB); occasionally misrecognises uncommon words.
- **AI occasionally breaks scene rules** — the LLM may introduce fantasy
  elements or repeat words despite prompt constraints.
- **spaCy / pydantic `ConfigError` on Python 3.14** — `ConfigError: unable
  to infer type for attribute "REGEX"`. Stick to Python 3.12; if you
  accidentally created a 3.14 env, drop it and recreate with
  `mamba create -n improv python=3.12 -y`.
- **`musicgen.py` fails with "PyTorch was not found"** — only happens if
  you uninstalled `torch` manually. Reinstall with `pip install torch`.
