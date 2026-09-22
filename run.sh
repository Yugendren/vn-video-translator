#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

echo "=================================================="
echo "   🎮 VN Video Translator & Localizer Pipeline"
echo "=================================================="

# Check ffmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "❌ Error: ffmpeg is not installed. Please install it with: brew install ffmpeg"
    exit 1
fi

# Check yt-dlp
if ! command -v yt-dlp &> /dev/null; then
    echo "⚠️ yt-dlp not found in PATH. It will be installed in the virtualenv."
fi

# Setup Virtualenv
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment (.venv)..."
    python3 -m venv .venv
fi

source .venv/bin/activate

# Install requirements
pip install -q -r requirements.txt

# Load .env if present
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Run translation pipeline
python3 translate.py "$@"
