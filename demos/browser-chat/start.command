#!/bin/bash
# Double-click on macOS to launch the demo.
# Starts a tiny local web server and opens the browser.

set -e
cd "$(dirname "$0")"
PORT=8000

# Find a free port if 8000 is taken
while lsof -i ":$PORT" >/dev/null 2>&1; do
  PORT=$((PORT + 1))
done

URL="http://localhost:$PORT"
echo "Browser Chat — serving from $(pwd)"
echo "Opening $URL"
( sleep 1 && open "$URL" ) &
exec python3 -m http.server "$PORT" --bind 127.0.0.1
