#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

# Quick bypass for help/about to print immediately without setup overhead
if [[ "$*" == *"--about"* ]] || [[ "$*" == *"-h"* ]] || [[ "$*" == *"--help"* ]]; then
    python3 translate.py "$@"
    exit 0
fi

echo "=================================================="
echo "   🎮 VN Video Translator & Localizer Pipeline"
echo "=================================================="

# Check ffmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "❌ Error: ffmpeg is not installed. Please install it with: brew install ffmpeg"
    exit 1
fi

# Setup Virtualenv
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment (.venv)..."
    python3 -m venv .venv
fi

source .venv/bin/activate

# Install requirements if not already marked installed
if [ ! -f ".venv/.installed" ]; then
    echo "📦 Installing Python dependencies..."
    pip install -q -r requirements.txt
    touch .venv/.installed
fi

# Load .env if present
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Run translation pipeline
python3 translate.py "$@"
