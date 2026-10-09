#!/usr/bin/env python3
"""Generate HomeLab Monitor PWA PNG icons from the dashboard brand colors."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

ACCENT = (37, 99, 235, 255)
WHITE = (255, 255, 255, 255)
NAVY = (15, 23, 42, 255)


def _chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def write_png(path: Path, size: int, pixels: list[tuple[int, int, int, int]]) -> None:
    raw = bytearray()
    for row in range(size):
        raw.append(0)
        start = row * size
        for pixel in pixels[start : start + size]:
            raw.extend(pixel)
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )
    path.write_bytes(payload)


def _fill(size: int, color: tuple[int, int, int, int]) -> list[tuple[int, int, int, int]]:
    return [color] * (size * size)


def _disk(
    pixels: list[tuple[int, int, int, int]],
    size: int,
    cx: float,
    cy: float,
    radius: float,
    color: tuple[int, int, int, int],
) -> None:
    r2 = radius * radius
    for y in range(size):
        for x in range(size):
            dx = x + 0.5 - cx
            dy = y + 0.5 - cy
            if dx * dx + dy * dy <= r2:
                pixels[y * size + x] = color


def _rect(
    pixels: list[tuple[int, int, int, int]],
    size: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: tuple[int, int, int, int],
) -> None:
    for y in range(max(0, y0), min(size, y1)):
        for x in range(max(0, x0), min(size, x1)):
            pixels[y * size + x] = color


def _round_rect(
    pixels: list[tuple[int, int, int, int]],
    size: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    radius: int,
    color: tuple[int, int, int, int],
) -> None:
    _rect(pixels, size, x0 + radius, y0, x1 - radius, y1, color)
    _rect(pixels, size, x0, y0 + radius, x1, y1 - radius, color)
    _disk(pixels, size, x0 + radius, y0 + radius, radius, color)
    _disk(pixels, size, x1 - radius, y0 + radius, radius, color)
    _disk(pixels, size, x0 + radius, y1 - radius, radius, color)
    _disk(pixels, size, x1 - radius, y1 - radius, radius, color)


def paint_mark(size: int, *, maskable: bool) -> list[tuple[int, int, int, int]]:
    pixels = _fill(size, ACCENT)
    inset = int(size * 0.22) if maskable else int(size * 0.12)
    inner = size - inset
    radius = max(6, size // 8)
    _round_rect(pixels, size, inset, inset, inner, inner, radius, NAVY)
    pad = inset + size // 8
    bar_w = max(3, size // 14)
    gap = max(4, size // 16)
    mark_h = inner - pad - size // 8
    x = pad + size // 16
    _rect(pixels, size, x, pad, x + bar_w, pad + mark_h, WHITE)
    _rect(pixels, size, x, pad, x + bar_w * 3, pad + bar_w, WHITE)
    x2 = x + bar_w * 3 + gap
    _rect(pixels, size, x2, pad, x2 + bar_w, pad + mark_h, WHITE)
    _rect(pixels, size, x2, pad + mark_h - bar_w, x2 + bar_w * 3, pad + mark_h, WHITE)
    _rect(pixels, size, x2 + bar_w * 2, pad, x2 + bar_w * 3, pad + mark_h, WHITE)
    return pixels


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "dashboard" / "public"
    icons = root / "icons"
    icons.mkdir(parents=True, exist_ok=True)
    write_png(icons / "icon-192.png", 192, paint_mark(192, maskable=False))
    write_png(icons / "icon-512.png", 512, paint_mark(512, maskable=False))
    write_png(icons / "icon-maskable-192.png", 192, paint_mark(192, maskable=True))
    write_png(icons / "icon-maskable-512.png", 512, paint_mark(512, maskable=True))
    write_png(root / "apple-touch-icon.png", 180, paint_mark(180, maskable=False))
    write_png(icons / "icon-32.png", 32, paint_mark(32, maskable=False))


if __name__ == "__main__":
    main()
