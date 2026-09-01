#!/usr/bin/env python3
"""Validate firmware-catalog.json: schema, file existence, offsets, SHA-256.

Exits 0 on success, 1 on any failure (used by CI to block deployment).
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "public" / "data" / "firmware-catalog.json"
PUBLIC = ROOT / "public"

REQUIRED_DEVICE_FIELDS = [
    "id", "manufacturer", "model", "firmware", "chipFamily",
    "flashSize", "version", "channel", "image", "factory", "update",
    "provenance",
]
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
BUILD_REF_RE = re.compile(r"^[0-9a-f]{7,40}$", re.IGNORECASE)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_offset(offset) -> int:
    if isinstance(offset, int):
        return offset
    s = str(offset).strip().lower()
    if s.startswith("0x"):
        s = s[2:]
    return int(s, 16)


def resolve_public_path(file_rel: str) -> Path:
    if not isinstance(file_rel, str) or not file_rel:
        raise ValueError("path must be a non-empty string")
    path = (PUBLIC / file_rel).resolve()
    if not path.is_relative_to(PUBLIC.resolve()):
        raise ValueError("path escapes public/")
    return path


def main() -> int:
    errors = []

    if not CATALOG.exists():
        print(f"FAIL: catalog not found: {CATALOG}")
        return 1

    try:
        data = json.loads(CATALOG.read_text())
    except json.JSONDecodeError as e:
        print(f"FAIL: catalog is not valid JSON: {e}")
        return 1

    devices = data.get("devices")
    if data.get("schemaVersion") != 1:
        errors.append("schemaVersion must be 1")
    if not isinstance(devices, list) or not devices:
        print("FAIL: catalog has no devices[]")
        return 1

    ids = set()
    for dev in devices:
        for field in REQUIRED_DEVICE_FIELDS:
            if field not in dev:
                errors.append(f"{dev.get('id', '?')}: missing field '{field}'")
        dev_id = dev.get("id")
        if not isinstance(dev_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", dev_id):
            errors.append(f"invalid device id: {dev_id!r}")
        if dev_id in ids:
            errors.append(f"duplicate device id: {dev_id}")
        ids.add(dev_id)

        image = dev.get("image")
        try:
            image_path = resolve_public_path(image)
            if not image_path.is_file():
                errors.append(f"{dev_id}: image not found: {image}")
        except ValueError as e:
            errors.append(f"{dev_id}: invalid image path ({e})")
        product_url = dev.get("productUrl")
        if product_url is not None and not str(product_url).startswith("https://"):
            errors.append(f"{dev_id}: productUrl must use https://")

        provenance = dev.get("provenance")
        if not isinstance(provenance, dict) or not provenance:
            errors.append(f"{dev_id}: provenance must be a non-empty object")
        else:
            for component, metadata in provenance.items():
                if not isinstance(metadata, dict):
                    errors.append(f"{dev_id}: provenance.{component} must be an object")
                    continue
                if not metadata.get("version"):
                    errors.append(f"{dev_id}: provenance.{component}.version is required")
                source = metadata.get("source")
                if source is not None and not str(source).startswith("https://"):
                    errors.append(f"{dev_id}: provenance.{component}.source must use https:// or be null")
                for ref_key in ("commit", "buildId"):
                    ref = metadata.get(ref_key)
                    if ref is not None and not BUILD_REF_RE.fullmatch(str(ref)):
                        errors.append(f"{dev_id}: provenance.{component}.{ref_key} is not a valid hex reference")
            meshtastic = provenance.get("meshtastic")
            if isinstance(meshtastic, dict) and meshtastic.get("version") != dev.get("version"):
                errors.append(f"{dev_id}: Meshtastic provenance version must match device version")

        wiring = dev.get("wiring")
        if dev.get("requiresExternalRadio") is True:
            if not isinstance(wiring, dict) or not isinstance(wiring.get("pins"), list) or not wiring["pins"]:
                errors.append(f"{dev_id}: external-radio target requires wiring.pins[]")
            else:
                for index, pin in enumerate(wiring["pins"]):
                    if not isinstance(pin, dict) or not pin.get("from") or not pin.get("to"):
                        errors.append(f"{dev_id}: wiring.pins[{index}] requires from and to labels")

        for plan_key in ("factory", "update"):
            plan = dev.get(plan_key)
            if not isinstance(plan, dict) or not isinstance(plan.get("parts"), list):
                errors.append(f"{dev_id}: {plan_key} must be an object with a parts[]")
                continue
            if not plan["parts"]:
                errors.append(f"{dev_id}: {plan_key}.parts is empty")
            for part in plan["parts"]:
                name = part.get("name", "?")
                file_rel = part.get("file")
                offset = part.get("offset")
                expected_sha = part.get("sha256")
                if not file_rel:
                    errors.append(f"{dev_id}/{plan_key}/{name}: missing file")
                    continue
                try:
                    fpath = resolve_public_path(file_rel)
                except ValueError as e:
                    errors.append(f"{dev_id}/{plan_key}/{name}: invalid file path ({e})")
                    continue
                if not fpath.is_file():
                    errors.append(f"{dev_id}/{plan_key}/{name}: file not found: {file_rel}")
                    continue
                if offset is None:
                    errors.append(f"{dev_id}/{plan_key}/{name}: missing offset")
                else:
                    try:
                        parse_offset(offset)
                    except (ValueError, TypeError):
                        errors.append(f"{dev_id}/{plan_key}/{name}: invalid offset {offset!r}")
                if expected_sha:
                    expected_sha_text = str(expected_sha).lower()
                    if not SHA256_RE.fullmatch(expected_sha_text):
                        errors.append(f"{dev_id}/{plan_key}/{name}: sha256 must be 64 hexadecimal characters")
                    actual = sha256(fpath)
                    if actual != expected_sha_text:
                        errors.append(
                            f"{dev_id}/{plan_key}/{name}: SHA-256 mismatch "
                            f"(catalog {expected_sha_text[:12]}… vs file {actual[:12]}…)"
                        )
                else:
                    errors.append(f"{dev_id}/{plan_key}/{name}: missing sha256")

        # --- loader (if declared) + loaderChanged consistency ---
        update = dev.get("update", {})
        loader = dev.get("loader")
        if update.get("loaderChanged") is True and not loader:
            errors.append(f"{dev_id}: loaderChanged=true but no loader metadata")
        if "loaderChanged" in update and not isinstance(update.get("loaderChanged"), bool):
            errors.append(f"{dev_id}: loaderChanged must be a boolean")
        if loader:
            lfile = loader.get("file")
            if not lfile:
                errors.append(f"{dev_id}: loader missing file")
            else:
                try:
                    lpath = resolve_public_path(lfile)
                except ValueError as e:
                    errors.append(f"{dev_id}: invalid loader path ({e})")
                    continue
                if not lpath.is_file():
                    errors.append(f"{dev_id}: loader file not found: {lfile}")
                elif loader.get("sha256"):
                    loader_sha = str(loader["sha256"]).lower()
                    if not SHA256_RE.fullmatch(loader_sha):
                        errors.append(f"{dev_id}: loader sha256 must be 64 hexadecimal characters")
                    actual = sha256(lpath)
                    if actual != loader_sha:
                        errors.append(
                            f"{dev_id}: loader SHA-256 mismatch "
                            f"(catalog {loader_sha[:12]}… vs file {actual[:12]}…)"
                        )
                else:
                    errors.append(f"{dev_id}: loader missing sha256")

    if errors:
        print("CATALOG VALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"CATALOG VALIDATION PASSED: {len(devices)} device(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
