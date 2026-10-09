#!/usr/bin/env python3
"""Inspect firmware binaries (size, SHA-256, basic ESP image info).

Read-only — never modifies binaries. Uses esptool.py image_info when available
(optional), otherwise reports size + hash only.
"""
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def esptool_image_info(path: Path) -> str:
    candidates = [
        shutil.which("esptool.py"),
        shutil.which("esptool"),
    ]
    for exe in candidates:
        if not exe:
            continue
        try:
            r = subprocess.run(
                [exe, "--chip", "esp32s3", "image_info", str(path)],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0:
                return r.stdout.strip()
        except Exception:
            continue
    return "(esptool not available)"


def main() -> int:
    files = sorted((PUBLIC / "firmware").rglob("*.bin"))
    if not files:
        print("No firmware binaries found under public/firmware")
        return 1

    for f in files:
        rel = f.relative_to(PUBLIC).as_posix()
        size = f.stat().st_size
        print(f"{rel}")
        print(f"  size:    {size} bytes ({size / (1024 * 1024):.2f} MiB)")
        print(f"  sha256:  {sha256(f)}")
        info = esptool_image_info(f)
        first = info.splitlines()[0] if info else ""
        print(f"  image:   {first}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
