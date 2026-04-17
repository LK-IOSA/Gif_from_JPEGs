#!/usr/bin/env python3
"""
gif_from_jpegs.py
-----------------
Walk a user-specified folder, read the modification timestamp of every JPEG,
sort the frames chronologically, assemble a GIF, and write a CSV that maps
each frame filename to its timestamp.

Energy-efficient design choices
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* Images are opened with ``Image.open()`` (lazy decode) and only decoded into
  memory when Pillow actually needs the pixel data for GIF encoding.
* Frames are thumbnailed to ``max_size`` *before* RGB→palette conversion so
  that only small images are kept in memory.  All frame objects are explicitly
  closed (file handles released) as soon as ``save()`` returns.
* Thumbnailing to ``max_size`` before encoding keeps both memory and I/O low
  when the source JPEGs are large.

Usage
-----
    python gif_from_jpegs.py <folder_path> [options]

Run ``python gif_from_jpegs.py --help`` for full option details.
"""

import argparse
import csv
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.exit(
        "Pillow is required.  Install it with:  pip install Pillow"
    )

# ── Supported JPEG extensions (case-insensitive) ─────────────────────────────
JPEG_EXTENSIONS = {".jpg", ".jpeg", ".jpe", ".jfif"}


def collect_jpegs(folder: Path) -> list[tuple[datetime, Path]]:
    """Return a list of (mtime, path) pairs for every JPEG in *folder*.

    Only the immediate contents of *folder* are scanned (non-recursive) so
    that accidental traversal of deeply-nested trees is avoided.
    The list is sorted by modification time ascending.
    """
    entries: list[tuple[datetime, Path]] = []
    for entry in os.scandir(folder):
        if not entry.is_file():
            continue
        if Path(entry.name).suffix.lower() not in JPEG_EXTENSIONS:
            continue
        mtime = datetime.fromtimestamp(entry.stat().st_mtime)
        entries.append((mtime, Path(entry.path)))

    entries.sort(key=lambda t: t[0])
    return entries


def _open_and_resize(path: Path, max_size: tuple[int, int]) -> Image.Image:
    """Open *path*, convert to RGB, thumbnail to *max_size*, return image."""
    img = Image.open(path)
    img = img.convert("RGB")
    img.thumbnail(max_size, Image.LANCZOS)
    return img


def build_gif(
    entries: list[tuple[datetime, Path]],
    output_path: Path,
    frame_duration_ms: int,
    max_size: tuple[int, int],
    loop: int,
) -> None:
    """Create an animated GIF from *entries* and save it to *output_path*.

    Parameters
    ----------
    entries:
        Sorted list of (mtime, jpeg_path) pairs.
    output_path:
        Destination ``.gif`` file.
    frame_duration_ms:
        Duration of each frame in milliseconds.
    max_size:
        Maximum (width, height); images are scaled down if larger.
    loop:
        Number of times the GIF loops (0 = infinite).
    """
    if not entries:
        raise ValueError("No JPEG files found — cannot create GIF.")

    first_frame = _open_and_resize(entries[0][1], max_size)
    rest = [_open_and_resize(path, max_size) for _, path in entries[1:]]

    try:
        first_frame.save(
            output_path,
            format="GIF",
            save_all=True,
            append_images=rest,
            duration=frame_duration_ms,
            loop=loop,
            optimize=True,
        )
    finally:
        # Release file handles promptly regardless of success or failure
        first_frame.close()
        for img in rest:
            img.close()


def write_csv(entries: list[tuple[datetime, Path]], csv_path: Path) -> None:
    """Write a CSV mapping each filename to its modification timestamp."""
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["filename", "datetime"])
        for mtime, path in entries:
            writer.writerow([path.name, mtime.strftime("%Y-%m-%d %H:%M:%S")])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create an animated GIF from all JPEGs in a folder, "
            "sorted by file modification time, and output a CSV "
            "with the timestamp of each frame."
        )
    )
    parser.add_argument(
        "folder",
        type=Path,
        help="Path to the folder containing the JPEG files.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help=(
            "Output GIF file path.  Defaults to <folder>/output.gif.  "
            "The CSV is written to the same directory with the same stem "
            "and a .csv extension."
        ),
    )
    parser.add_argument(
        "--duration",
        "-d",
        type=int,
        default=500,
        metavar="MS",
        help="Duration of each frame in milliseconds (default: 500).",
    )
    parser.add_argument(
        "--max-width",
        type=int,
        default=800,
        metavar="PX",
        help="Maximum frame width in pixels (default: 800).",
    )
    parser.add_argument(
        "--max-height",
        type=int,
        default=600,
        metavar="PX",
        help="Maximum frame height in pixels (default: 600).",
    )
    parser.add_argument(
        "--loop",
        type=int,
        default=0,
        metavar="N",
        help=(
            "Number of times the GIF loops.  0 = infinite (default: 0)."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    folder: Path = args.folder.resolve()
    if not folder.is_dir():
        print(f"Error: '{folder}' is not a directory.", file=sys.stderr)
        return 1

    print(f"Scanning '{folder}' for JPEG files …")
    entries = collect_jpegs(folder)

    if not entries:
        print("No JPEG files found in the specified folder.", file=sys.stderr)
        return 1

    print(f"Found {len(entries)} JPEG file(s).")

    # Determine output paths
    if args.output is None:
        gif_path = folder / "output.gif"
    else:
        gif_path = args.output.resolve()

    csv_path = gif_path.with_suffix(".csv")

    max_size = (args.max_width, args.max_height)

    print(f"Building GIF → '{gif_path}' …")
    build_gif(entries, gif_path, args.duration, max_size, args.loop)
    print(f"GIF saved:  {gif_path}")

    print(f"Writing CSV → '{csv_path}' …")
    write_csv(entries, csv_path)
    print(f"CSV saved:  {csv_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
