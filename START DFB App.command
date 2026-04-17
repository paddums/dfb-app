#!/bin/bash

# Add all common Python locations to PATH (covers Homebrew, system Python, pyenv etc.)
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

# Find this script's folder reliably
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "================================================"
echo "  DFB Training Assistant"
echo "================================================"
echo ""

# Find python3 — check common Mac locations
PYTHON=""
for p in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3 python3; do
  if command -v "$p" &>/dev/null; then
    PYTHON="$p"
    break
  fi
done

if [ -z "$PYTHON" ]; then
  echo "Python3 not found."
  echo ""
  echo "Please install it by opening Terminal and typing:"
  echo "   xcode-select --install"
  echo ""
  echo "Then try this launcher again."
  read -p "Press Enter to close..."
  exit 1
fi

echo "Python found: $PYTHON"
echo ""

# Install required packages
echo "Checking required packages..."
$PYTHON -m pip install anthropic flask flask-cors --quiet --break-system-packages 2>/dev/null || \
$PYTHON -m pip install anthropic flask flask-cors --quiet 2>/dev/null
echo "Packages ready."
echo ""

# Check the API key
KEY=$(grep "ANTHROPIC_API_KEY=" .env 2>/dev/null | cut -d'=' -f2 | tr -d '[:space:]')
if [ -z "$KEY" ] || [ "$KEY" = "paste-your-key-here" ]; then
  echo "No API key found in .env file."
  echo "Please open the .env file and add your key."
  read -p "Press Enter to close..."
  exit 1
fi
echo "API key found."
echo ""

# Open the browser after a 3 second delay
sleep 3 && open "$SCRIPT_DIR/index.html" &

echo "Starting server... leave this window open while using the app."
echo "To stop: press CTRL+C or close this window."
echo ""
$PYTHON app.py
