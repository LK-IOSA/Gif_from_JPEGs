"""
tests/test_gif_from_jpegs.py
-----------------------------
Unit and integration tests for gif_from_jpegs.py.
"""

import csv
import os
import time
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image

# Make sure the repo root is on sys.path so the script can be imported
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

import gif_from_jpegs as gfj


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_jpeg(path: Path, color: tuple = (255, 0, 0)) -> Path:
    """Save a tiny solid-colour JPEG at *path* and return *path*."""
    img = Image.new("RGB", (40, 30), color)
    img.save(path, format="JPEG")
    return path


# ── collect_jpegs ─────────────────────────────────────────────────────────────

class TestCollectJpegs:
    def test_returns_only_jpeg_files(self, tmp_path):
        _make_jpeg(tmp_path / "a.jpg")
        _make_jpeg(tmp_path / "b.jpeg")
        (tmp_path / "c.png").write_bytes(b"fake-png")
        (tmp_path / "d.txt").write_text("hello")

        result = gfj.collect_jpegs(tmp_path)
        names = {p.name for _, p in result}
        assert names == {"a.jpg", "b.jpeg"}

    def test_sorted_by_mtime(self, tmp_path):
        paths = [_make_jpeg(tmp_path / f"{i}.jpg") for i in range(3)]
        # Stagger modification times so the sort has work to do
        now = time.time()
        for offset, p in enumerate(paths):
            os.utime(p, (now + offset * 10, now + offset * 10))

        result = gfj.collect_jpegs(tmp_path)
        mtimes = [mt for mt, _ in result]
        assert mtimes == sorted(mtimes)

    def test_empty_folder_returns_empty_list(self, tmp_path):
        assert gfj.collect_jpegs(tmp_path) == []

    def test_case_insensitive_extension(self, tmp_path):
        _make_jpeg(tmp_path / "upper.JPG")
        _make_jpeg(tmp_path / "mixed.Jpeg")
        result = gfj.collect_jpegs(tmp_path)
        assert len(result) == 2

    def test_non_recursive(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        _make_jpeg(sub / "nested.jpg")
        result = gfj.collect_jpegs(tmp_path)
        assert result == []


# ── build_gif ─────────────────────────────────────────────────────────────────

class TestBuildGif:
    def _entries(self, tmp_path, n=3):
        paths = [_make_jpeg(tmp_path / f"{i}.jpg", (i * 80, 0, 0)) for i in range(1, n + 1)]
        now = time.time()
        entries = []
        for offset, p in enumerate(paths):
            t = now + offset
            os.utime(p, (t, t))
            entries.append((datetime.fromtimestamp(t), p))
        return entries

    def test_creates_gif_file(self, tmp_path):
        entries = self._entries(tmp_path)
        gif_path = tmp_path / "out.gif"
        gfj.build_gif(entries, gif_path, frame_duration_ms=200, max_size=(100, 100), loop=0)
        assert gif_path.exists()
        assert gif_path.stat().st_size > 0

    def test_gif_has_correct_frame_count(self, tmp_path):
        n = 4
        entries = self._entries(tmp_path, n=n)
        gif_path = tmp_path / "out.gif"
        gfj.build_gif(entries, gif_path, frame_duration_ms=200, max_size=(100, 100), loop=0)

        with Image.open(gif_path) as img:
            frame_count = 0
            try:
                while True:
                    frame_count += 1
                    img.seek(img.tell() + 1)
            except EOFError:
                pass
        assert frame_count == n

    def test_raises_on_empty_entries(self, tmp_path):
        with pytest.raises(ValueError, match="No JPEG files found"):
            gfj.build_gif([], tmp_path / "out.gif", 200, (100, 100), 0)

    def test_max_size_respected(self, tmp_path):
        """Output frames must not exceed max_size."""
        # Create a large source image
        big = tmp_path / "big.jpg"
        Image.new("RGB", (1000, 800), (100, 150, 200)).save(big, format="JPEG")
        now = time.time()
        entries = [(datetime.fromtimestamp(now), big)]

        gif_path = tmp_path / "out.gif"
        gfj.build_gif(entries, gif_path, frame_duration_ms=200, max_size=(100, 100), loop=0)

        with Image.open(gif_path) as img:
            assert img.width <= 100
            assert img.height <= 100


# ── write_csv ─────────────────────────────────────────────────────────────────

class TestWriteCsv:
    def test_csv_has_header_and_rows(self, tmp_path):
        entries = [
            (datetime(2024, 1, 15, 10, 30, 0), Path("img1.jpg")),
            (datetime(2024, 1, 15, 11, 45, 0), Path("img2.jpg")),
        ]
        csv_path = tmp_path / "output.csv"
        gfj.write_csv(entries, csv_path)

        with csv_path.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.reader(fh))

        assert rows[0] == ["filename", "datetime"]
        assert rows[1] == ["img1.jpg", "2024-01-15 10:30:00"]
        assert rows[2] == ["img2.jpg", "2024-01-15 11:45:00"]

    def test_csv_row_count_matches_entries(self, tmp_path):
        entries = [(datetime(2024, 1, i, 0, 0, 0), Path(f"{i}.jpg")) for i in range(1, 6)]
        csv_path = tmp_path / "output.csv"
        gfj.write_csv(entries, csv_path)

        with csv_path.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
        # header + 5 data rows
        assert len(rows) == 6


# ── parse_args ────────────────────────────────────────────────────────────────

class TestParseArgs:
    def test_defaults(self, tmp_path):
        args = gfj.parse_args([str(tmp_path)])
        assert args.folder == tmp_path
        assert args.output is None
        assert args.duration == 500
        assert args.max_width == 800
        assert args.max_height == 600
        assert args.loop == 0

    def test_custom_options(self, tmp_path):
        out = tmp_path / "my.gif"
        args = gfj.parse_args([
            str(tmp_path),
            "--output", str(out),
            "--duration", "250",
            "--max-width", "320",
            "--max-height", "240",
            "--loop", "3",
        ])
        assert args.output == out
        assert args.duration == 250
        assert args.max_width == 320
        assert args.max_height == 240
        assert args.loop == 3


# ── main (integration) ────────────────────────────────────────────────────────

class TestMain:
    def test_end_to_end(self, tmp_path):
        """Full pipeline: folder -> GIF + CSV."""
        for i, color in enumerate([(200, 0, 0), (0, 200, 0), (0, 0, 200)]):
            p = _make_jpeg(tmp_path / f"{i}.jpg", color)
            t = time.time() + i * 5
            os.utime(p, (t, t))

        rc = gfj.main([str(tmp_path)])
        assert rc == 0

        gif_path = tmp_path / "output.gif"
        csv_path = tmp_path / "output.csv"
        assert gif_path.exists()
        assert csv_path.exists()

        with csv_path.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
        assert rows[0] == ["filename", "datetime"]
        assert len(rows) == 4  # header + 3 frames

    def test_missing_folder_returns_error(self, tmp_path):
        rc = gfj.main([str(tmp_path / "does_not_exist")])
        assert rc == 1

    def test_empty_folder_returns_error(self, tmp_path):
        rc = gfj.main([str(tmp_path)])
        assert rc == 1

    def test_custom_output_path(self, tmp_path):
        _make_jpeg(tmp_path / "img.jpg")
        gif_out = tmp_path / "subdir" / "result.gif"
        gif_out.parent.mkdir()
        rc = gfj.main([str(tmp_path), "--output", str(gif_out)])
        assert rc == 0
        assert gif_out.exists()
        assert (gif_out.parent / "result.csv").exists()
