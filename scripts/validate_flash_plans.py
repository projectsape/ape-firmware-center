#!/usr/bin/env python3
"""Critical flash-plan validation.

Guards against:
- UPDATE/FACTORY confusion (eraseAll flags, factory artifacts in update)
- artifacts that exceed the flash size (start + size > flash_size)
- overlapping artifacts within the same plan
- loader inclusion rules (loaderChanged)

Exits 0 on success, 1 on failure — a failure means DO NOT DEPLOY.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "public" / "data" / "firmware-catalog.json"
PUBLIC = ROOT / "public"


def parse_offset(offset) -> int:
    if isinstance(offset, int):
        return offset
    s = str(offset).strip().lower()
    if s.startswith("0x"):
        s = s[2:]
    return int(s, 16)


def flash_size_bytes(flash_size) -> int:
    s = str(flash_size).strip().upper()
    table = {
        "1MB": 1 << 20, "2MB": 2 << 20, "4MB": 4 << 20,
        "8MB": 8 << 20, "16MB": 16 << 20, "32MB": 32 << 20,
    }
    if s not in table:
        raise ValueError(f"unknown flash size {flash_size!r}")
    return table[s]


def collect_plan_parts(dev) -> dict:
    """Return {plan_name: [part_dict, ...]}. The loader is added to the UPDATE
    plan only when the release explicitly marks it changed (loaderChanged)."""
    plans = {}
    for plan_name in ("factory", "update"):
        plan = dev.get(plan_name, {})
        parts = list(plan.get("parts", []))
        if plan_name == "update" and dev.get("loader") and plan.get("loaderChanged") is True:
            loader = dev["loader"]
            parts = parts + [{
                "name": "loader",
                "file": loader.get("file"),
                "offset": loader.get("offset"),
            }]
        plans[plan_name] = parts
    return plans


def find_bounds_errors(dev_id, plan_name, parts, fsize, public_dir: Path):
    """Each artifact must satisfy: start >= 0, size > 0, start+size <= fsize."""
    errors = []
    for p in parts:
        name = p.get("name", "?")
        file_rel = p.get("file", "")
        try:
            offset = parse_offset(p.get("offset"))
        except (ValueError, TypeError):
            errors.append(f"{dev_id}/{plan_name}/{name}: invalid offset")
            continue
        fpath = public_dir / file_rel
        if not fpath.exists():
            errors.append(f"{dev_id}/{plan_name}/{name}: file not found: {file_rel}")
            continue
        size = fpath.stat().st_size
        end = offset + size
        if offset < 0 or size <= 0 or end > fsize:
            errors.append(
                f"{dev_id}/{plan_name}/{name}: exceeds flash: "
                f"offset=0x{offset:x} size=0x{size:x} end=0x{end:x} "
                f"flash_size=0x{fsize:x}"
            )
    return errors


def find_overlap_errors(dev_id, plan_name, parts, public_dir: Path):
    """No two artifacts in the same plan may overlap. Adjacent ranges (A.end ==
    B.start) are valid."""
    errors = []
    ranges = []
    for p in parts:
        name = p.get("name", "?")
        file_rel = p.get("file", "")
        try:
            offset = parse_offset(p.get("offset"))
        except (ValueError, TypeError):
            continue
        fpath = public_dir / file_rel
        size = fpath.stat().st_size if fpath.exists() else 0
        ranges.append((name, file_rel, offset, offset + size))

    for i in range(len(ranges)):
        for j in range(i + 1, len(ranges)):
            a_name, a_file, a_start, a_end = ranges[i]
            b_name, b_file, b_start, b_end = ranges[j]
            if a_end <= b_start or b_end <= a_start:
                continue  # disjoint or adjacent — valid
            errors.append(
                f"{dev_id}/{plan_name}: overlapping artifacts "
                f"{a_name} [0x{a_start:x},0x{a_end:x}) and "
                f"{b_name} [0x{b_start:x},0x{b_end:x})"
            )
    return errors


def main() -> int:
    data = json.loads(CATALOG.read_text())
    devices = data.get("devices", [])
    errors = []

    for dev in devices:
        dev_id = dev.get("id")
        update = dev.get("update", {})
        factory = dev.get("factory", {})

        # --- UPDATE plan ---
        if update.get("eraseAll") is not False:
            errors.append(f"{dev_id}: update.eraseAll must be false")
        uparts = list(update.get("parts", []))
        fparts = list(factory.get("parts", []))
        ffiles = {p.get("file") for p in fparts}
        for p in uparts:
            if p.get("file") in ffiles:
                errors.append(f"{dev_id}: update part {p.get('name')} points to a factory artifact")
        if not uparts:
            errors.append(f"{dev_id}: update.parts is empty")

        # --- FACTORY plan ---
        if factory.get("eraseAll") is not True:
            errors.append(f"{dev_id}: factory.eraseAll must be true")
        if not fparts:
            errors.append(f"{dev_id}: factory.parts is empty")

        # --- loaderChanged consistency ---
        if update.get("loaderChanged") is True and not dev.get("loader"):
            errors.append(f"{dev_id}: loaderChanged=true but no loader metadata")
        if "loaderChanged" in update and not isinstance(update.get("loaderChanged"), bool):
            errors.append(f"{dev_id}: loaderChanged must be a boolean")

        # --- flash size + bounds + overlaps ---
        try:
            fsize = flash_size_bytes(dev.get("flashSize"))
        except ValueError as e:
            errors.append(f"{dev_id}: {e}")
            continue

        plans = collect_plan_parts(dev)
        for plan_name, parts in plans.items():
            errors += find_bounds_errors(dev_id, plan_name, parts, fsize, PUBLIC)
            errors += find_overlap_errors(dev_id, plan_name, parts, PUBLIC)

    if errors:
        print("\nDO NOT DEPLOY — flash plan validation failed:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("\nFLASH PLAN VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
