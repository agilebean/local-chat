#!/bin/bash
# Double-click on macOS to launch the demo.
# Uses the localai mamba env if available (enables Kokoro TTS);
# otherwise falls back to system python3 (Browser TTS only).

set -e
cd "$(dirname "$0")"

PORT=8000
while lsof -i ":$PORT" >/dev/null 2>&1; do
  PORT=$((PORT + 1))
done
export PORT

URL="http://localhost:$PORT"
echo "Browser Chat — serving from $(pwd)"
echo "Opening $URL"
( sleep 1.5 && open "$URL" ) &

# Pick the best Python interpreter available.
for prefix in "$HOME/Software/miniforge3" "$HOME/miniforge3" "$HOME/miniconda3" "$HOME/anaconda3" "/opt/miniforge3"; do
  if [ -x "$prefix/envs/localai/bin/python" ]; then
    echo "Using $prefix/envs/localai (Kokoro TTS available)"
    exec "$prefix/envs/localai/bin/python" server.py
  fi
done

if command -v mamba >/dev/null 2>&1 && mamba env list 2>/dev/null | grep -q "^localai "; then
  echo "Using mamba run -n localai (Kokoro TTS available)"
  exec mamba run -n localai --live-stream python server.py
fi

echo "localai env not found — running with system python3 (Browser TTS only)"
exec python3 server.py
