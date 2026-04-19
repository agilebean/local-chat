# Browser Chat

A tiny conversational AI that runs **entirely in your browser** — no install,
no API key, no server-side compute. ~350 MB model downloads to your browser
cache once, then works offline.

## Run it

### macOS (easiest)

Double-click `start.command`. A Terminal window opens, the local server
starts, and your browser opens to the demo.

### Bash alias (Mac/Linux)

If `~/.bash_aliases` is sourced from your shell, the `browserchat` alias
goes to this folder, activates the `improv` mamba env, and launches the
demo in one step:

```bash
browserchat
```

### Any platform (manual)

```bash
cd improv/demos/browser-chat
python3 -m http.server 8000
```

Then open <http://localhost:8000> in **Chrome 113+, Edge, or Safari 26+**
(WebGPU required). Pick a model, click "Load model", wait for the one-time
download, type, and chat.

### Why not just double-click `index.html`?

You can't. Three things on the page need a real `http://` origin:

1. The Web-LLM library is loaded as an ES module from a CDN. Browsers
   refuse to run `<script type="module">` from `file://`.
2. `llm_config.json` and `friend.txt` are loaded with `fetch()`, which
   is blocked by CORS on `file://`.
3. WebGPU itself requires a **secure context**: `localhost`, `127.0.0.1`,
   or `https://`. `file://` doesn't qualify in Chrome.

The local server requirement is one command (or one double-click).

## What's in the box

```
demos/browser-chat/                  ~20 KB total
├── index.html              # the entire app (UI + chat loop)
├── llm_config.json         # model list + sampling + prompt filename
├── friend.txt              # bundled copy of the friend persona prompt
├── start.command           # macOS double-click launcher
└── README.md
```

## Features

- **Model pulldown**: Qwen2.5-0.5B (default), SmolLM2-360M, Qwen2.5-1.5B.
- **Streaming**: token-by-token responses.
- **Speak replies**: native browser `SpeechSynthesis` (toggle off if it
  interrupts demo flow).
- **Reset chat**: clear conversation, keep model loaded.

## Why WebGPU and not Transformers.js / WASM

Web-LLM uses MLC's compiled WGSL kernels on the GPU. On Apple Silicon this
gives **~50–80 tok/s decode** for the default 0.5B model — roughly 5–10×
faster than ONNX/Transformers.js running on the CPU. Latency matters in a
live demo: at 5 tok/s a 2-sentence reply takes 8 seconds; at 60 tok/s it
takes under a second.

Trade-off: WebGPU is Chrome 113+ / Edge / Safari 26+ only. No WASM fallback.

## Where the prompt comes from

Canonical prompts live one level up at [`../../prompts/`](../../prompts/),
shared with the Python improv loop. `friend.txt` here is a synced bundle so
the demo is self-contained when zipped and shared with students.

To re-sync after editing the canonical prompt (run from the improv repo root):

```bash
python3 -c "from src.prompts import load_prompt; print(load_prompt('friend','system'))" \
  > demos/browser-chat/friend.txt
```

To demo a different persona, edit `friend.txt` directly (or re-sync from
`../../prompts/<persona>.md`) and update `system_prompt_file` in
`llm_config.json` if you rename the file.
