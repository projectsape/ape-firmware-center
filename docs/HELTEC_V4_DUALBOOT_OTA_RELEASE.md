# Heltec V4 DualBoot with OTA

## Current release — UI v4 loader on the DualBoot v1 layout — 2026-10-10

Owner-authorized publication of the Heltec V4 DualBoot OTA product. The exact
applications already flashed and readback-verified on the board are reused for
the factory image, the USB update and the signed OTA feed, so all three paths
install identical bytes:

- MeshCore `v1.17.1` — 1,271,264 bytes, SHA256
  `019b1a7be443b828b91931b09fd56d462e30ad61104e23c72b715752778f6f70`
- Meshtastic `2.8.1.2a8d5a2` — 2,298,880 bytes, SHA256
  `4bb042f4bac160a8d9d9679644c5b81a8b7b16bd997e22f9f223f389c52664b0`
- Loader `UIv4-20261010` — 1,026,768 bytes, SHA256
  `d9208b6f245a435073e72301468b541ff1eac3a8bc6db6dca26ddc0e36bb22a5`

This webflasher distributes compiled firmware and operational metadata, not
firmware source packages.

## DualBoot v1 layout

Approved partition map, `ape-heltec-v4-dualboot-ota-v1`:

| partition | type | offset | size |
| --- | --- | --- | --- |
| nvs | data/nvs | 0x009000 | 0x006000 |
| otadata | data/ota | 0x00f000 | 0x002000 |
| loader_nvs | data/nvs | 0x011000 | 0x00f000 |
| loader | app/factory | 0x020000 | 0x180000 |
| meshcore | app/ota_0 | 0x1a0000 | 0x200000 |
| meshtas | app/ota_1 | 0x3a0000 | 0x300000 |
| core_fs | data/spiffs | 0x6a0000 | 0x4b0000 |
| tastic_fs | data/spiffs | 0xb50000 | 0x4b0000 |

The published reference sector `firmware/heltec-v4/update/partitions-ota-v1.bin`
is the exact one-sector image stored at `0x8000` in the factory.

## USB update and layout guard

An UPDATE never erases: MeshCore is written at `0x1a0000` and Meshtastic at
`0x3a0000`. This release sets `loaderChanged: true`, so the loader is written at
`0x20000`. NVS, loader_nvs and both filesystems stay outside every write.

Before any write, and again at the write boundary, the flasher reads the
installed `0x8000` sector (4096 bytes) and compares it with the SHA-verified
catalog artifact. A device still carrying the previous Heltec V4 layout is
refused instead of being converted in place: it must run **Clean install**,
which erases the device. The guard is also re-checked after the port is
selected, the artifacts downloaded and the chip/flash model verified, so no
cached approval survives a changed connection or plan.

## Signed OTA feed

- Feed: `https://projectsape.github.io/ape-firmware-center/firmware/heltec-v4/update`
- Board `heltec-v4-dualboot`, layout `ape-heltec-v4-dualboot-ota-v1`
- Schema 3 manifests signed with the P-256 key published as
  `firmware/heltec-v4/ota-public-key.pem`; the private signing key stays outside
  this repository.
- The loader embeds the same public key, pins the feed URL, and verifies TLS
  with the ESP-IDF certificate bundle. Plain HTTP and insecure TLS are refused;
  there is no bench interface in the production loader.

## Artifacts

- `firmware/heltec-v4/factory/APE-Heltec-V4-DualBoot-OTA-20261010-b3377c0b33db4433.factory.bin`
  — 16 MiB, SHA256 `b3377c0b33db4433b909dfc2b553ca953fe4710452cd6da99c705ce4319c0a0e`
- `firmware/heltec-v4/update/loader-d9208b6f245a4350.bin`
- `firmware/heltec-v4/update/partitions-ota-v1.bin`
- `firmware/heltec-v4/update/meshcore/{manifest.json,meshcore-019b1a7be443b828.bin}`
- `firmware/heltec-v4/update/meshtastic/{manifest.json,meshtastic-4bb042f4bac160a8.bin}`
- `firmware/heltec-v4/release.json`

The factory shares every byte with the board-verified 16 MiB image except the
loader slot `0x20000`–`0x19ffff`, which now carries this release's loader with
erased padding, and the application slots, which hold the same bytes as the
signed feed.

## Verification performed

- `validate_catalog.py`, `validate_flash_plans.py` (+13 tests) and
  `validate_ota_release.py` (T147 section plus the new Heltec V4 section): PASS.
- `test_ota_release.py` — 45 gate tests, including the 17 Heltec V4 tamper gates
  (signature, signed commit/version, application bytes, factory loader, manifest
  path, legacy `0xA0000` offset, guard removal, flash-size bypass, loader offset,
  bench build, bench key, firmware-source entries): OK.
- `validate_binary_distribution.py` / `validate_source_privacy.py` on `public/`
  and on the built `dist/`: PASS (binaries and metadata only).
- `generate_checksums.py --check`: OK.
- `npm test`: 47/47 (catalog resolution, loaderChanged inclusion, and the new
  Heltec V4 USB guard tests).
- Loader host suite (`run_candidate_host.py`): 21/21, including the production
  TLS contract (public CA bundle, hostname verification kept, no private CA).
- On board: the factory install, loader-only updates and a full signed-OTA
  reinstall of both applications with these exact application bytes were
  verified on the Heltec V4 R2; the published feed check from the device follows
  this publication.

## Publication history

- 2026-10-10 — Heltec V4 DualBoot UI v4 loader, layout `ape-heltec-v4-dualboot-ota-v1`,
  signed feed, USB layout guard, new factory. Owner-authorized.
