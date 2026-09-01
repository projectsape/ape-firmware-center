# Projects APE Flasher

Flash and update **APE firmware** directly from your browser via **USB / Web Serial**.

A public, static web application — no backend, no accounts, no tracking. The
flasher is built on [esptool-js](https://github.com/espressif/esptool-js). Web
flashing requires a desktop browser that exposes Web Serial (current Chrome or
Edge) and a USB data cable.

Every firmware artifact is SHA-256 checked against the catalog before a flash
write begins. This is a download-integrity check, not a digital signature or an
independent authentication of the publisher.

## Supported hardware

| Device | Firmware | Chip | Flash |
| --- | --- | --- | --- |
| Heltec V3 | APE DualBoot | ESP32-S3 | 8 MB |
| Heltec V4 | APE DualBoot | ESP32-S3 | 16 MB |
| Waveshare T147 LoRa | Meshtastic (LoRa) | ESP32-S3 | 16 MB |
| Waveshare T147 No-LoRa | Meshtastic (No-LoRa) | ESP32-S3 | 16 MB |

## Two install modes

- **WIPE & INSTALL (FACTORY)** — a clean install. Erases the entire flash and
  writes the APE factory image to the documented offsets. Any existing
  firmware, settings and data may be destroyed.
- **UPDATE EXISTING APE** — writes only the declared update partitions and
  **never** performs a full erase. It is intended **only** for a device already
  running the corresponding APE target/layout. It does **not** inspect what
  firmware or layout was previously installed. Stored data is not guaranteed,
  and updating an incompatible layout may require a clean reinstall.

The flasher **never inspects the existing firmware** on the device and never
auto-detects your hardware. It only performs a chip-family check and (where
supported) a physical flash-size check. Selecting the correct device and mode
is your responsibility.

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
4. `python3 scripts/generate_checksums.py --check` — checksums consistent.
5. `npm test` — web-app behavior (SHA-256 verification before flash, chip-family,
   flash-size, loaderChanged, reset/serial monitor).
6. `npm run build` → deploy to GitHub Pages over HTTPS.

A failing validation blocks deployment.

## Licensing

- **Web app code** (`src/`, `scripts/`, `index.html`) — MIT. See `LICENSE`.
- **esptool-js** (flasher engine) — Apache License 2.0, npm dependency.
- **APE firmware binaries** (`public/firmware/`) — **GPL-3.0**, derived from
  Meshtastic (GPL-3.0) + MeshCore (MIT). See `THIRD_PARTY_LICENSES.md`.
- **Logo and board imagery** — owner rights reserved. See `ASSET_SOURCES.md`.

### Source provenance

Every device in `public/data/firmware-catalog.json` carries a `provenance`
object recording, per component, the version, upstream source repository and
commit identifier where known. Unknown values are left `null` (pending) rather
than invented. The web interface exposes these values and labels missing source
links explicitly. To satisfy the GPL-3.0 obligation for the distributed binaries:

- **Meshtastic** — https://github.com/meshtastic/firmware (GPL-3.0)
- **MeshCore** — https://github.com/meshcore-dev/MeshCore (MIT)
- **APE DualBoot loader** — custom; source pending publication

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
