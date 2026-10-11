# Projects APE Flasher

Browser-based flasher and update site for Projects APE firmware on ESP32-S3 boards.
Everything runs locally in the browser through the Web Serial API — firmware,
catalog and flash logs never leave your computer. Built on
[esptool-js](https://github.com/espressif/esptool-js).

**Live site:** https://projectsape.github.io/ape-firmware-center/

## Supported devices

| Device | Firmware | Chip | Flash |
| --- | --- | --- | --- |
| Heltec V3 | APE DualBoot | ESP32-S3 | 8 MB |
| Heltec V4 | APE DualBoot + Wi-Fi OTA | ESP32-S3 | 16 MB |
| Waveshare T147 LoRa | WadaMesh + Meshtastic DualBoot + Wi-Fi OTA | ESP32-S3 | 16 MB |
| Waveshare T147 No-LoRa | Meshtastic (No-LoRa) | ESP32-S3 | 16 MB |

## Installation modes

- **UPDATE EXISTING APE** — writes the update partitions for the selected target and
  never performs a full erase. Use it only on a device already running that APE
  layout: T147 DualBoot and Heltec V4 verify the installed partition table before
  any write. The loader slot is written only when a release marks the loader
  changed. T147 DualBoot and Heltec V4 also update from the device's own Wi-Fi OTA
  menu; the loader itself is always USB-only.
- **CLEAN INSTALL — ERASES ALL** — erases the whole flash and writes the factory
  image. Firmware, settings and stored data are removed. Use it for a first install
  or to convert a standalone Meshtastic board to DualBoot.

Boards are not auto-detected: select the exact model and mode yourself. A mismatched
target is refused by the layout guard instead of being converted in place.

## How to flash

1. Open the live site in desktop Chrome or Edge (mobile browsers do not expose Web
   Serial).
2. Pick your device and installation mode.
3. Complete the responsibility checkboxes (T147 LoRa also asks you to verify the
   external SX1262 wiring).
4. Connect the board with a USB data cable and select its serial port.
5. Flash → verify → reset. Written flash is read back and verified against the
   catalog image.

## Firmware

The catalog (`public/data/firmware-catalog.json`) pins every artifact by SHA-256,
and each download is checked before a write begins. Wi-Fi OTA updates are delivered
as signed P-256 schema-3 manifests; the loader verifies signature, version, size and
the installed identity before installing. Only compiled firmware and operational
metadata are published here — never firmware source.

Release details and artifact hashes: [`docs/FIRMWARE.md`](docs/FIRMWARE.md).

## Development

```bash
npm install
npm run dev        # local dev server (localhost is a secure context)
npm run build      # production build into dist/
```

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

To add a device: drop the firmware under `public/firmware/<id>/{factory,update}/`,
add its catalog entry, add a board image under `public/assets/boards/`, and
regenerate checksums (`python3 scripts/generate_checksums.py`). No app code changes
are needed.

## Validation and deployment

Pushing to `main` runs the repository validators and test suites — catalog, flash
plans, signed OTA release, source privacy, binary-only distribution, checksums,
`npm test` and `npm run build` — then deploys `dist/` to GitHub Pages. A failing
check blocks deployment.

## Licensing

- Web app code (`src/`, `scripts/`, `index.html`) — MIT. See `LICENSE`.
- esptool-js — Apache-2.0, npm dependency.
- Firmware applications — Meshtastic and WadaMesh: GPL-3.0; MeshCore: MIT.
- APE loaders — separate components distributed as compiled binaries only; their
  implementation source is private.
- Logo and board photography — owner rights reserved. See
  [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md).

## Troubleshooting

- No serial port listed: use desktop Chrome/Edge, a USB **data** cable, close other
  serial tools and reconnect the board.
- Bootloader mode differs per board; follow the manufacturer's documented sequence
  instead of assuming a universal one.
- After an interrupted or incompatible update, reconnect the same target and retry.
  A clean install recovers a known-good layout, erasing data.

## Disclaimer

APE firmware and the flasher are experimental community projects provided as-is,
without warranty. Flashing carries risks including configuration loss, data loss
or a device that needs manual recovery. Use at your own risk.
