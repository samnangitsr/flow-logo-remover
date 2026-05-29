# Veo3 Logo Remover

A small cross-platform desktop app (Python + PyQt6) that removes the Flow **Veo3**
logo / watermark from videos you generated. Open a video, mark the watermark box
(there's a one-click bottom-right preset for the Flow Veo wordmark), pick a removal
method, and export a cleaned MP4 with the audio preserved.

> Only use this on videos you have the right to edit. Removing watermarks may be
> against the terms of service of the tool that produced them.

## Features

- Load `mp4 / mov / mkv / webm / avi` files (anything ffmpeg can read).
- Scrub to any frame to preview where the logo sits.
- Select the logo region by dragging on the preview, typing exact pixel
  coordinates, or using the **Veo3 bottom-right preset**.
- Two removal back-ends:
  - **Delogo** – ffmpeg's `delogo` filter; fast and blends from surrounding
    pixels. Best default.
  - **Inpaint** – per-frame OpenCV Telea inpainting; slower, sometimes cleaner
    on busy backgrounds.
- Audio is preserved.
- Progress bar + cancel, runs off the UI thread.

## Requirements

- Python 3.10+
- [`ffmpeg`](https://ffmpeg.org/) and `ffprobe` available on your `PATH`.
  - macOS: `brew install ffmpeg`
  - Debian/Ubuntu: `sudo apt install ffmpeg`
  - Windows: download from the ffmpeg site and add the `bin` folder to `PATH`.

## Install & run

```bash
python -m pip install -r requirements.txt
python -m veo3_logo_remover
```

Or install as a command:

```bash
python -m pip install .
veo3-logo-remover
```

## How removal works

`delogo` replaces the marked rectangle by interpolating from the pixels just
outside it, so it needs a 1px border inside the frame — corner boxes are nudged
inward automatically. If the result looks smeared on a detailed background, try
the **Inpaint** method instead, or shrink the box to hug the watermark.

## Development

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest
```

Tests cover the geometry/clamping logic and ffmpeg command construction (no GUI
or display required).
