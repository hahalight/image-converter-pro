# 🖼 Image Converter Pro

[![Build & Release](https://github.com/YOUR_USERNAME/image-converter-pro/actions/workflows/build.yml/badge.svg)](https://github.com/YOUR_USERNAME/image-converter-pro/actions/workflows/build.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

A lightweight, cross-platform image conversion tool built with Python & Tkinter.

---

## ✨ Features

| Feature | Details |
|---------|---------|
| **Format conversion** | PNG · JPEG · WEBP · BMP · TIFF · GIF · APNG · ICO · AVIF · TGA |
| **Resize** | Pixel-perfect with optional aspect-ratio lock |
| **Alpha channel** | Full transparency preserved for PNG / WEBP / APNG / GIF / AVIF |
| **Animated images** | GIF ↔ WEBP ↔ APNG re-encode with per-frame control |
| **Sequence → Frames** | Extract every frame from any animated file |
| **Frames → Animation** | Assemble still images into GIF / WEBP / APNG |
| **Batch mode** | Convert entire folders in one click |

---

## 🖥 Installation

### Option A — Pre-built binary (Windows / Linux / macOS)

Download the latest release from the [Releases page](../../releases).

| Platform | File |
|----------|------|
| Windows 10/11 | `ImageConverterPro-Windows-x64.zip` |
| Linux | `ImageConverterPro-Linux-x64.tar.gz` |
| macOS | `ImageConverterPro-macOS-x64.zip` |

### Option B — Run from source

```bash
git clone https://github.com/YOUR_USERNAME/image-converter-pro.git
cd image-converter-pro
pip install -r requirements.txt
python src/main.py
```

### Option C — Docker (Linux binary build)

```bash
# Build the Docker image and extract the binary
docker build --target linux-build -t imgconv-builder .
mkdir -p dist
docker run --rm -v "$PWD/dist":/out imgconv-builder

# Run the binary
./dist/ImageConverterPro
```

---

## 🐳 Docker Development Environment

```bash
# Linux with X11 forwarding (GUI)
xhost +local:docker
docker compose --profile dev up

# Just build Linux binary
docker compose --profile linux up
```

---

## 🔨 Building from source (Windows, no Docker)

```powershell
pip install -r requirements.txt
pip install pyinstaller

pyinstaller ImageConverterPro.spec --noconfirm
# Output: dist/ImageConverterPro.exe
```

---

## 🧪 Running tests

```bash
pip install pytest
pytest tests/ -v
```

---

## 📁 Project structure

```
image-converter-pro/
├── src/
│   ├── main.py          # Entry point
│   ├── converter.py     # Conversion engine (no GUI deps)
│   └── gui.py           # Tkinter UI
├── tests/
│   └── test_converter.py
├── .github/
│   └── workflows/
│       └── build.yml    # CI/CD: build EXE + create Release
├── Dockerfile
├── docker-compose.yml
├── ImageConverterPro.spec
├── requirements.txt
└── README.md
```

---

## 🔧 GitHub Actions — Automatic builds

Every push of a version tag (`v*.*.*`) triggers a build for all three platforms and creates a GitHub Release with download links.

```bash
# Tag and push to trigger a release build
git tag v1.0.0
git push origin v1.0.0
```

You can also trigger a build manually from the **Actions** tab → **Build & Release** → **Run workflow**.

---

## 📝 License

MIT © 2024 — see [LICENSE](LICENSE) for details.
