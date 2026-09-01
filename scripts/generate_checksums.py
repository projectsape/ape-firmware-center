#!/usr/bin/env python3
"""Generate (or verify) checksums/SHA256SUMS.txt for all published firmware.

Usage:
  python3 generate_checksums.py            # write SHA256SUMS.txt
  python3 generate_checksums.py --check    # verify existing file (CI)
"""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
SUMS = ROOT / "checksums" / "SHA256SUMS.txt"


def collect() -> dict:
    """Return {rel_path_from_public: sha256} for every *.bin under public/firmware."""
    out = {}
    for f in sorted((PUBLIC / "firmware").rglob("*.bin")):
        rel = f.relative_to(PUBLIC).as_posix()
        h = hashlib.sha256()
        h.update(f.read_bytes())
        out[rel] = h.hexdigest()
    return out


def parse_sums(path: Path) -> dict:
    out = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2:
            continue
        out[parts[1]] = parts[0]
    return out


def main() -> int:
    files = collect()
    lines = [f"{h}  {rel}" for rel, h in files.items()]

    if "--check" in sys.argv:
        if not SUMS.exists():
            print("FAIL: SHA256SUMS.txt missing")
            return 1
        on_disk = parse_sums(SUMS)
        ok = True
        for rel, h in files.items():
            if on_disk.get(rel) != h:
                print(f"FAIL: checksum mismatch for {rel}")
                ok = False
        for rel in on_disk:
            if rel not in files:
                print(f"FAIL: SHA256SUMS.txt lists missing file {rel}")
                ok = False
        if ok:
            print(f"CHECKSUMS OK: {len(files)} file(s)")
            return 0
        return 1

    SUMS.parent.mkdir(parents=True, exist_ok=True)
    SUMS.write_text("\n".join(lines) + "\n")
    print(f"Wrote {SUMS} ({len(files)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
