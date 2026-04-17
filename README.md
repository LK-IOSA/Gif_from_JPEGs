# Gif_from_JPEGs

A command-line pipeline that walks a user-specified folder, reads the
**file-system modification timestamp** of every JPEG it finds (no timestamp
in the filename required), sorts the frames chronologically, assembles an
animated GIF, and writes a companion CSV that records the filename and
datetime of every frame.

---

## Requirements

- Python 3.10+
- [Pillow](https://pillow.readthedocs.io/)

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Usage

```
python gif_from_jpegs.py <folder> [options]
```

| Argument / Option | Default | Description |
|---|---|---|
| `folder` | *(required)* | Path to the folder containing the JPEG files. |
| `--output` / `-o` | `<folder>/output.gif` | Output GIF file path. The CSV is placed in the same directory with the same stem and a `.csv` extension. |
| `--duration` / `-d` | `500` | Duration of each frame in milliseconds. |
| `--max-width` | `800` | Maximum frame width in pixels (images are scaled down proportionally if larger). |
| `--max-height` | `600` | Maximum frame height in pixels. |
| `--loop` | `0` | Number of GIF loops (0 = infinite). |

### Examples

```bash
# Basic: create output.gif and output.csv inside the target folder
python gif_from_jpegs.py /path/to/photos

# Custom output location, 1-second frames, max 1920x1080
python gif_from_jpegs.py /path/to/photos \
    --output /path/to/timelapse.gif \
    --duration 1000 \
    --max-width 1920 \
    --max-height 1080
```

---

## Outputs

| File | Contents |
|---|---|
| `output.gif` (or custom name) | Animated GIF assembled from all JPEGs in chronological order. |
| `output.csv` (same stem) | Two-column CSV: `filename`, `datetime` (format `YYYY-MM-DD HH:MM:SS`). |

Example CSV:

```
filename,datetime
IMG_0001.jpg,2024-06-01 08:00:00
IMG_0002.jpg,2024-06-01 08:05:00
IMG_0003.jpg,2024-06-01 08:10:00
```

---

## Energy-efficient design

- Images are opened lazily and thumbnailed **before** palette conversion,
  minimising peak memory usage.
- Only the minimum pixel data required for GIF encoding is kept in memory at
  any one time — all other frames are released immediately after encoding.
- The `optimize=True` flag is passed to Pillow's GIF encoder to reduce output
  file size.

---

## Running the tests

```bash
pip install pytest Pillow
python -m pytest tests/ -v
```
