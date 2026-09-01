#!/usr/bin/env python3
"""Generate web-ready APE branding and board imagery from preserved originals."""
from __future__ import annotations

import re
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "public" / "assets"
LOGO_SOURCE = Path(
    "/home/enmanuels/Dev/Heltec-Release/candidates/"
    "v3-dualboot-2.8.0-ape-20260823/src/graphics/img/ape_logo.xbm"
)


def load_ape_xbm(path: Path) -> Image.Image:
    text = path.read_text()
    width = int(re.search(r"ape_logo_width\s+(\d+)", text).group(1))
    height = int(re.search(r"ape_logo_height\s+(\d+)", text).group(1))
    body = re.search(r"ape_logo_bits\[\].*?=\s*\{(.*?)\};", text, re.S).group(1)
    values = [int(value, 16) for value in re.findall(r"0x([0-9A-Fa-f]{2})", body)]
    stride = (width + 7) // 8
    if len(values) != stride * height:
        raise ValueError(f"Unexpected XBM length: {len(values)}")

    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pixels = image.load()
    ink = (222, 216, 200, 255)
    for y in range(height):
        for x in range(width):
            byte = values[y * stride + (x // 8)]
            if byte & (1 << (x % 8)):
                pixels[x, y] = ink
    return image


def border_background_mask(arr: np.ndarray, threshold: int) -> np.ndarray:
    """Mask True where the border-connected near-black background is.

    Only near-black pixels (max channel <= threshold) that are connected to an
    image border count as background. Interior dark pixels (bezel, LCD content)
    are preserved.
    """
    h, w = arr.shape[:2]
    candidate = arr.max(axis=2) <= threshold
    visited = np.zeros((h, w), dtype=bool)
    q: deque[tuple[int, int]] = deque()

    for x in range(w):
        for y in (0, h - 1):
            if candidate[y, x] and not visited[y, x]:
                visited[y, x] = True
                q.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if candidate[y, x] and not visited[y, x]:
                visited[y, x] = True
                q.append((y, x))

    while q:
        y, x = q.popleft()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx] and candidate[ny, nx]:
                visited[ny, nx] = True
                q.append((ny, nx))
    return visited


def box_blur(alpha: np.ndarray, radius: int = 2) -> np.ndarray:
    """Cheap box blur (edge-padded) to feather a binary alpha edge."""
    h, w = alpha.shape
    k = radius * 2 + 1
    a = np.pad(alpha.astype(np.float32), radius, mode="edge")
    acc = np.zeros_like(alpha, dtype=np.float32)
    for i in range(k):
        for j in range(k):
            acc += a[i : i + h, j : j + w]
    return (acc / (k * k)).astype(np.uint8)


def t147_transparent(source: Path, out: Path) -> None:
    arr = np.asarray(Image.open(source).convert("RGB"))
    mask = border_background_mask(arr, threshold=12)
    alpha = box_blur(np.where(mask, 0, 255).astype(np.uint8), radius=2)

    rgba = np.dstack([arr, alpha]).astype(np.uint8)
    img = Image.fromarray(rgba, "RGBA")

    bbox = Image.fromarray((alpha > 8).astype(np.uint8), "L").getbbox()
    if bbox:
        pad = 12
        left = max(0, bbox[0] - pad)
        top = max(0, bbox[1] - pad)
        right = min(img.width, bbox[2] + pad)
        bottom = min(img.height, bbox[3] + pad)
        img = img.crop((left, top, right, bottom))

    img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
    img.save(out, "WEBP", quality=90, method=6)


def main() -> None:
    logo_dir = ASSETS / "logo"
    originals = logo_dir / "originals"
    originals.mkdir(parents=True, exist_ok=True)
    (originals / "ape-logo.xbm").write_text(LOGO_SOURCE.read_text())

    logo = load_ape_xbm(LOGO_SOURCE)
    logo.resize((1024, 512), Image.Resampling.NEAREST).save(
        logo_dir / "ape-logo.webp", "WEBP", lossless=True, method=6
    )
    logo.resize((256, 128), Image.Resampling.NEAREST).save(
        logo_dir / "ape-logo.png", "PNG", optimize=True
    )

    icon = Image.new("RGB", (512, 512), (10, 12, 14))
    icon_logo = logo.resize((416, 208), Image.Resampling.NEAREST)
    icon.paste(icon_logo, ((512 - 416) // 2, (512 - 208) // 2), icon_logo)
    icon.save(logo_dir / "ape-icon.png", "PNG", optimize=True)

    social = Image.new("RGB", (1200, 630), (10, 12, 14))
    social_logo = logo.resize((840, 420), Image.Resampling.NEAREST)
    social.paste(social_logo, ((1200 - 840) // 2, (630 - 420) // 2), social_logo)
    social.save(logo_dir / "ape-social-card.png", "PNG", optimize=True)

    board_originals = ASSETS / "boards" / "originals"
    for board_id in ("heltec-v3", "heltec-v4"):
        source = board_originals / f"{board_id}-heltec.png"
        image = Image.open(source).convert("RGBA")
        image.save(
            ASSETS / "boards" / f"{board_id}.webp",
            "WEBP",
            quality=88,
            method=6,
        )

    t147_transparent(
        board_originals / "t147-user-provided.jpg",
        ASSETS / "boards" / "t147.webp",
    )


if __name__ == "__main__":
    main()
