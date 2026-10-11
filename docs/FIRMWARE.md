# Firmware releases

This repository publishes compiled firmware and the metadata the flasher needs.
Every artifact is pinned by SHA-256 in the catalog and verified before any write.
Here are the current releases per device and the history of what has been
published.

## Waveshare T147 LoRa DualBoot — WadaMesh + Meshtastic + OTA

Current release: **WadaMesh beta_90** (2026-10-09). The published WadaMesh image is
the exact binary flashed and read back on hardware; USB, OTA and factory carry the
same bytes.

| Artifact | Slot | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `wadamesh-08e625cdbfddc46a.bin` | `0x1a0000` | 3291728 | `08e625cdbfddc46a1f309f8e62e7a1c776f84ae462afe85841c32e2235dce841` |
| `meshtastic-abd30fd015aaed5c.bin` | `0x520000` | 3764096 | `abd30fd015aaed5c627814f572912571ed4b42384f351dfd8cfb4058678fdfdf` |
| `loader-3b44fb49fe56adf2.bin` | `0x20000` | 1289104 | `3b44fb49fe56adf2e237ce232eb261dd1a5988d970ff8c9a7e26bd6a04051e61` |
| `APE-T147-LoRa-DualBoot-OTA-20261009-afd00ab3ead3b41b.factory.bin` | `0x0` | 16777216 | `afd00ab3ead3b41b282bf45bfa4cb839917fc69537637d847a8a5ee2c0a4f036` |

- WadaMesh `v1.17.4-touch` (upstream commit `39f342c6`); Meshtastic stays on
  `2.8.1.f7ad9dc`, unchanged from the previous release.
- A USB update writes both applications without a full erase; this release sets
  `loaderChanged: false`, so it does not touch the loader (`Legacy-20261007`,
  automatic update checks after Wi-Fi).
- Layout `ape-t147-dualboot-ota-v2`. OTA feed:
  `https://projectsape.github.io/ape-firmware-center/firmware/t147-dualboot/update`
  — one operation at a time, manual Test and Confirm.

## Waveshare T147 NoLoRa — Meshtastic

| Artifact | Slot | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `T147-NoLoRa.meshtastic.bin` | `0x10000` | 3724480 | `4634529315f5e666409cc0c88d7092f5ac863fc6190a71bbbbc7c6772be6683a` |
| `T147-NoLoRa.factory.bin` | `0x0` | 3790016 | `b163c5cd19ed07d689835f511465858e04b5c83c622d96d6f45dfc143aab2151` |
| `T147-NoLoRa.littlefs.bin` | `0xC90000` | 3538944 | `2025b200ef42e636a5258f8db9f734a855dfb91a8a36c3c2bbdc5ea2f0ce92c6` |

Meshtastic `2.8.1` without the external LoRa radio; stable since 2026-09-23. The
USB update writes the application at `0x10000` without a full erase.

## Heltec V4 DualBoot with OTA

Current release: loader **`UIv4.5c-20261010`** (2026-10-10).

| Artifact | Slot | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `meshcore-019b1a7be443b828.bin` | `0x1a0000` | 1271264 | `019b1a7be443b828b91931b09fd56d462e30ad61104e23c72b715752778f6f70` |
| `meshtastic-4bb042f4bac160a8.bin` | `0x3a0000` | 2298880 | `4bb042f4bac160a8d9d9679644c5b81a8b7b16bd997e22f9f223f389c52664b0` |
| `partitions-ota-v1.bin` | `0x8000` (reference sector) | 4096 | `23353614a32bd5d4213e986be966c09076ba94232b740097d2f9089f89779ba1` |
| `loader-2aa4b3da757219c3.bin` | `0x20000` | 1012048 | `2aa4b3da757219c312033fad2d9072c7e1af197d7780bfe2dc8f2eb9a8e62d75` |
| `APE-Heltec-V4-DualBoot-OTA-20261010-c02af3a24d0c57ed.factory.bin` | `0x0` | 16777216 | `c02af3a24d0c57ed39ad6048ea3a6a4de9b9007997edc0733e4d95661a0731c5` |

- Loader changes: BACK parity with the T147 loader (the button is serviced before
  automatic OTA work; CANCEL while busy, BACK when idle; a cancelled exit no longer
  relaunches a check) and the loop-task stack raised to 16 KiB so entering OTA
  cannot trip the stack canary.
- Layout `ape-heltec-v4-dualboot-ota-v1`:

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

- A USB update writes MeshCore, Meshtastic and — when the release marks it — the
  loader, without erasing. Before writing, the flasher compares the installed
  `0x8000` sector with `partitions-ota-v1.bin`; a device on a different layout is
  refused and must use Clean install.
- OTA feed: `https://projectsape.github.io/ape-firmware-center/firmware/heltec-v4/update`
  with schema-3 P-256 manifests. The loader pins the feed URL, embeds the public
  key and verifies TLS against the ISRG roots (X1/X2) — no plain HTTP, no fallback.

## Heltec V3 DualBoot

| Artifact | Slot | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `meshcore.bin` | `0xA0000` | 1272736 | `1500bfff38db8d37fbedd4fb096560c1b864710a349fc204356eb5c6cd348d68` |
| `meshtastic.bin` | `0x300000` | 2276336 | `243cc0b88a6eaf6730ed481812e04ffe2fd571f182e4a9ed09340e1e3d5e9702` |
| `loader.bin` | `0x20000` | 290976 | `3ba56a44e1d78c790f3850a4f99f82987fcec5789a68bc4e357b7353790b9bf4` |
| `ape-dualboot-heltec-v3-8mb.bin` | `0x0` | 8388608 | `2392558ac66d137ed606f9208f07beb4166e525c59b06f137a1a3374671ddeaa` |

8 MB variant, stable since 2026-09-23; the loader is not written by updates.

## Signing and integrity

- The catalog SHA-256 is a download-integrity check, not a signature.
- OTA manifests are schema 3 with DER P-256 ECDSA/SHA-256 signatures. The
  verification public key (`ota-public-key.pem`) is published per device; the
  private signing key is not in this repository.
- Only compiled binaries and operational metadata are published — firmware source
  is not hosted here. Third-party licenses: see `THIRD_PARTY_LICENSES.md`.

## Updating and rollback

- **UPDATE** writes the declared update partitions and never erases. **CLEAN
  INSTALL** erases the whole flash and writes the factory image.
- The loader slot is USB-only, written only when a release marks the loader
  changed; OTA never rewrites it.
- Previous immutable artifacts remain in the repository history. On a configured
  board, restore an older loader over the guarded USB path — applications and data
  survive. Restoring an older factory is a clean install and erases configuration.

## Previous releases

T147 LoRa DualBoot:

- `Legacy-20261004` r2 — an image installed by the web flasher (raw bytes, no NVS
  write) now adopts its manifest identity instead of showing `CURRENT: Unknown`
  (`loader-513e1165…`, factory `…5d905f27…`).
- `Legacy-20261004` — selector UI refinement: elongated choices, camo title,
  larger OTA controls, pagination; no Ready labels (`loader-fee3a067…`, factory
  `…aaad8a43…`).
- `Legacy-20261003` — first Legacy publication (`loader-e5b92e8e…`, factory
  `…a9aa2d32…`).

Heltec V4:

- `UIv4.4` — fixes the selector countdown expiring the instant BACK was pressed in
  OTA (an unsigned `millis()` underflow; signed deltas now, as in the T147).
- `UIv4.2` / `UIv4.3` — leaving OTA re-arms a fresh five-second countdown for the
  last application, surviving a residual button hold.
- `UIv4.1` — application cards simplified; the update check runs automatically.

## Publishing a release

1. Freeze the layout, loader, public key and unchanged applications; an
   application-only release reuses its exact accepted bytes.
2. Stage the factory, signed manifests, immutable binaries, metadata and catalog.
   For an application-only release, replace the slot in the current published
   factory — never reassemble from an older one — and update only that
   application's USB part and manifest.
3. Run the local pipeline: catalog, flash-plan and OTA validators, rejection
   tests, checksums, `npm test`, `npm run build`.
4. Review the catalog diff; confirm other devices are unchanged.
5. Publish only with explicit approval; a green local run is not authorization.
6. After deployment, re-fetch the public manifests and verify signatures, hashes
   and factory parity.
7. Acceptance test: a real HTTPS update with manual Test/Confirm on a board.
