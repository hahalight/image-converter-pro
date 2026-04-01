# ─────────────────────────────────────────────────────────────────
# Image Converter Pro — Docker Build Environment
#
# Purpose : Install dependencies + PyInstaller, then build
#           a Windows-compatible executable via Wine or a
#           Linux-native binary (choose target at build time).
#
# Usage (Linux/Mac native binary):
#   docker build --target linux-build -t imgconv-builder .
#   docker run --rm -v "%cd%/dist":/out imgconv-builder
#
# Usage (Wine cross-compile for Windows exe):
#   docker build --target wine-build -t imgconv-wine-builder .
#   docker run --rm -v "%cd%/dist":/out imgconv-wine-builder
# ─────────────────────────────────────────────────────────────────

# ── Stage 1: base dependencies ────────────────────────────────────
FROM python:3.11-slim AS base

WORKDIR /app

# System packages needed by Pillow, tkinter, and pillow-avif
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-tk \
        tk-dev \
        libavif-dev \
        libfreetype6-dev \
        libjpeg62-turbo-dev \
        libpng-dev \
        libtiff-dev \
        libwebp-dev \
        libopenjp2-7-dev \
        liblcms2-dev \
        libffi-dev \
        zlib1g-dev \
        upx-ucl \
        binutils \
        git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir pyinstaller

# ── Stage 2: Linux native build ───────────────────────────────────
FROM base AS linux-build

COPY . .

RUN pyinstaller ImageConverterPro.spec \
        --distpath /out \
        --workpath /tmp/build \
        --noconfirm

CMD ["echo", "Linux build done — binary is in /out"]

# ── Stage 3: Wine-based Windows cross-compile ─────────────────────
FROM base AS wine-build

RUN dpkg --add-architecture i386 \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        wine \
        wine32 \
        wine64 \
        winetricks \
    && rm -rf /var/lib/apt/lists/*

# Download Python 3.11 Windows installer and set up Wine prefix
ENV WINEARCH=win64 WINEPREFIX=/root/.wine64
RUN wineboot --init \
    && winetricks --unattended vcrun2022 || true

# NOTE: For a true Windows exe you should install Python-for-Windows
# inside Wine and then run PyInstaller there. This Dockerfile shows
# the scaffold — the GitHub Actions workflow handles the actual
# Windows EXE build natively via windows-latest runner.

COPY . .

CMD ["echo", "Wine cross-compile scaffold ready. See GitHub Actions for Windows EXE."]
