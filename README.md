# VN Video Translator

An automated pipeline designed to download, transcribe via native Apple Silicon Vision OCR, translate with lore accuracy, and render localized dialogue overlays onto Visual Novel and game cutscene videos.

Produces both hardcoded 1080p MP4 videos and standalone `.srt` subtitle files.

---

## Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/yugendren/vn-video-translator.git
cd vn-video-translator
```

### 2. Prerequisites
Requires macOS with Homebrew installed:
```bash
brew install ffmpeg yt-dlp
```

### 3. Run Pipeline
Add your video links to `links.txt`, then run:
```bash
./run.sh
```

---

## Translation Engines

The pipeline supports two translation engines:

| Feature | Option 1: Gemini Flash (Cloud) | Option 2: Local Model (llama.cpp) |
| :--- | :--- | :--- |
| **Best For** | Studio-quality localization, tone & character nuances | Offline usage, privacy, bulk processing |
| **Cost** | ~$0.001 per 30-minute episode | Free |
| **Speed** | 3 to 5 seconds per episode | ~45 seconds on Apple Silicon GPU |
| **Setup** | Free API key from [Google AI Studio](https://aistudio.google.com/app/apikey) | Auto-downloads Qwen 2.5 3B (~2.0 GB) |

### Option 1 Setup (Gemini Flash)
On first launch, the CLI prompts for your free Google AI Studio key and offers to save it automatically to `.env`. Alternatively, set it in your environment:
```bash
export GEMINI_API_KEY="your_api_key_here"
```

### Option 2 Setup (Local Qwen Model)
No API key or account required. If `llama.cpp` or the recommended model (`Qwen2.5-3B-Instruct`) is missing, the CLI offers to install and download them automatically.

---

## Common Commands

### Batch Processing
Process all URLs listed in `links.txt`:
```bash
./run.sh
```

### Single Video via Option 1 (Cloud)
```bash
./run.sh "https://www.bilibili.com/video/BV1sbhk6GEtY?p=1" --engine 1 --lore gfl2
```

### Single Video via Option 2 (Local)
```bash
./run.sh "https://www.bilibili.com/video/BV1sbhk6GEtY?p=1" --engine 2 --font latex
```

### Append Link and Run Immediately
```bash
./run.sh --add-link "https://www.bilibili.com/video/BV..."
```

### Process Local MP4 File
```bash
./run.sh /path/to/recording.mp4
```

### Quick Help and Flag Reference
```bash
./run.sh --help
./run.sh --about
```

---

## Typography Options

- `--font latex`: STIX Two Text (default authentic LaTeX book serif)
- `--font arial`: Clean modern sans-serif
- `--font times`: Classic roman serif
- `--font /path/to/font.ttf`: Any custom TTF/OTF font file

Dialogue lines stay fixed at `28pt` by default. Long lines automatically downscale dynamically to prevent dialogue box overflow or edge collision.

---

## Technical Documentation

For detailed architecture diagrams, Apple Neural Engine OCR specifications, typewriter de-duplication algorithms, lore configuration schemas, and full parameter references, see [DETAILS.md](DETAILS.md).

---

## License

MIT License. See [LICENSE](LICENSE) for details.
