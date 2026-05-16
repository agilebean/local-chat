# Next steps — 2026-05-16

After shared-migration: speech — tts + stt from agentkit.

## To do

1. **Rename mamba env** from `localai` to `local-chat` — consistent with repo name.
2. **Fix STT wait time** — current STT waits 30s for silence before cutting. Revert to previous shorter timeout implementation.
