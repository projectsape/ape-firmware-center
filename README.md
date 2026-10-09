# Projects APE Flasher

Flash and update **APE firmware** directly from your browser via **USB / Web Serial**.

A public, static web application — no backend, no accounts, no tracking. The
flasher is built on [esptool-js](https://github.com/espressif/esptool-js). Web
flashing requires a desktop browser that exposes Web Serial (current Chrome or
Edge) and a USB data cable.

This repository is a webflasher, not a firmware build archive. Public firmware
delivery contains compiled binaries and required catalog/OTA metadata. Firmware
source trees, source packages and private build evidence stay outside this repo.

Every firmware artifact is SHA-256 checked against the catalog before a flash
write begins. This is a download-integrity check, not a digital signature or an
independent authentication of the publisher.

## Supported hardware

| Device | Firmware | Chip | Flash |
| --- | --- | --- | --- |
| Heltec V3 | APE DualBoot | ESP32-S3 | 8 MB |
| Heltec V4 | APE DualBoot | ESP32-S3 | 16 MB |
| Waveshare T147 LoRa | WadaMesh + Meshtastic DualBoot + Wi-Fi OTA | ESP32-S3 | 16 MB |
| Waveshare T147 No-LoRa | Meshtastic (No-LoRa) | ESP32-S3 | 16 MB |

## Two install modes

- **WIPE & INSTALL (FACTORY)** — a clean install. Erases the entire flash and
  writes the APE factory image to the documented offsets. Any existing
  firmware, settings and data may be destroyed.
- **UPDATE EXISTING APE** — writes only the declared update partitions and
  **never** performs a full erase. It is intended **only** for a device already
  running the corresponding APE target/layout. Each target keeps its declared
  update plan; **T147 DualBoot** updates WadaMesh and Meshtastic over USB and
  includes the loader slot only when a release marks the loader changed, after
  verifying 16MB flash and the exact installed OTA-v2 partition sector. The
  same apps also update from the device OTA menu.

The flasher does not auto-detect board models. T147 DualBoot updates add a
partition-layout check before any write, including a repeat check at the
write boundary. Incompatible standalone Meshtastic needs a clean installation
to convert to DualBoot; that conversion erases settings. NoLoRa remains unchanged.
The previous standalone LoRa build is retained locally only. The public T147
choices are LoRa DualBoot OTA and NoLoRa Meshtastic.

The T147 OTA feed uses signed P-256 schema-3 manifests from GitHub Pages, with
independent WadaMesh/Meshtastic packages, one operation at a time and manual Test /
Confirm. The Source page is read-only; production always uses the official URL.
See [the release procedure](docs/T147_DUALBOOT_OTA_RELEASE.md).

## How it works

1. Pick your device.
2. Choose **UPDATE** or **WIPE & INSTALL**.
3. Accept the responsibility checkboxes (and verify wiring for T147 LoRa).
4. Connect the board over USB (Web Serial — desktop Chrome/Edge).
5. Flash → verify → reset.

## Repository layout

```
index.html              landing page
src/                    web app (vanilla JS + esptool-js)
public/firmware/        compiled firmware (.bin) per device
public/data/            firmware-catalog.json (single source of truth)
checksums/              SHA256SUMS.txt
scripts/                validation + checksum tooling
.github/workflows/      GitHub Actions → GitHub Pages deploy
```

### Adding a device

1. Add firmware artifacts under `public/firmware/<id>/{factory,update}/`.
2. Add an entry to `public/data/firmware-catalog.json`.
3. Add a board image under `public/assets/boards/`.
4. Regenerate checksums: `python3 scripts/generate_checksums.py`.

No app code changes required.

## Development

```bash
npm install
npm run dev        # local dev server (localhost is a secure context)
npm run build      # production build into dist/
```

## Validation & CI

Pushing to `main` runs:

1. `python3 scripts/validate_catalog.py` — files exist, JSON valid, SHA-256 match.
2. `python3 scripts/validate_flash_plans.py` — update `eraseAll=false`, factory
   `eraseAll=true`, no update part points at a factory image, offsets in range,
   every artifact within the flash bounds, no overlapping artifacts, and
   loader-inclusion rules.
3. `python3 scripts/test_flash_plans.py` — unit tests for flash-plan bounds,
   overlap and loader rules.
4. `python3 scripts/validate_ota_release.py` — P-256 signatures, ESP checksums,
   factory/app/loader/table correspondence and USB guards.
5. `python3 scripts/test_ota_release.py` — corrupt/unsafe-package rejection.
6. `python3 scripts/validate_source_privacy.py public` and
   `python3 scripts/test_source_privacy.py` — reject private loader sources and
   metadata. `python3 scripts/test_binary_distribution.py` and
   `python3 scripts/validate_binary_distribution.py public` additionally forbid
   firmware source packages, renamed archives and source-download metadata.
7. `python3 scripts/generate_checksums.py --check` — checksums consistent.
8. `npm test` — web-app behavior (SHA-256 verification before flash, chip-family,
   flash-size, loaderChanged, reset/serial monitor).
9. `npm run build` followed by both privacy and binary-distribution validators
   on `dist/` → deploy to GitHub Pages over HTTPS.

A failing validation blocks deployment.

## Licensing

- **Web app code** (`src/`, `scripts/`, `index.html`) — MIT. See `LICENSE`.
- **esptool-js** (flasher engine) — Apache License 2.0, npm dependency.
- **Third-party firmware applications** (`public/firmware/`) — keep their
  upstream licenses: the Meshtastic and WadaMesh applications are **GPL-3.0**
  and the MeshCore components are **MIT**. Binary-only packaging does not remove
  applicable corresponding-source obligations. See `THIRD_PARTY_LICENSES.md`.
- **APE T147 loader** — a separate APE firmware component, distributed as a
  compiled binary. Its implementation source is private and is not published.
- **Logo and board imagery** — owner rights reserved. See `ASSET_SOURCES.md`.

### Source provenance

Every device in `public/data/firmware-catalog.json` carries a `provenance`
object recording, per component, the version, upstream source repository and
commit identifier where known. Unknown values are left `null` (pending) rather
than invented. The web interface exposes these values and labels missing upstream
links explicitly. It does not offer firmware source-package downloads.
The independent APE T147 loader is a separate firmware component; its
implementation source is not included in the current public release. Its source
commit is not recorded because none is available.

Removing files from the current tree or rewriting public history cannot recall
third-party downloads or guarantee removal from GitHub caches and fork networks.
This packaging policy does not purport to revoke rights granted by an applicable
license.

The upstream application projects are:

- **Meshtastic** — https://github.com/meshtastic/firmware (GPL-3.0)
- **WadaMesh** — https://github.com/ALLFATHER-BV/wadamesh (GPL-3.0)
- **MeshCore** — https://github.com/meshcore-dev/MeshCore (MIT)

## Connection and recovery

- If no port is listed, use desktop Chrome or Edge, verify that the cable
  carries data, close other serial tools and reconnect the board.
- Bootloader button sequences differ by product. Follow the board
  manufacturer's documented download-mode procedure rather than assuming one
  universal BOOT/RESET sequence.
- After an interrupted or incompatible update, reconnect the same target and
  retry. **WIPE & INSTALL** can recover a clean layout, but erases the entire
  flash including firmware, settings and stored data.
- Report reproducible flasher problems in
  [GitHub Issues](https://github.com/projectsape/ape-firmware-center/issues).

## Disclaimer

APE firmware and Projects APE Flasher are **experimental community projects
provided free of charge and without warranty**. Flashing carries inherent risks
including configuration loss, data loss, failed boot, or the need to manually
recover a device. Use at your own risk.
