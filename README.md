# Projects APE Flasher

Browser-based flasher and update site for Projects APE firmware on ESP32-S3 boards.
USB flashing runs locally in the browser through the Web Serial API. Firmware
and release metadata are downloaded from this site; flash logs are not uploaded. Built on
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
  layout: Heltec V3, Heltec V4 and T147 DualBoot verify the installed partition
  table during preparation and again before writing. The loader slot is written only when a release marks the loader
  changed. T147 DualBoot and Heltec V4 also update from the device's own Wi-Fi OTA
  menu; the loader itself is always USB-only.
- **CLEAN INSTALL — ERASES ALL** — erases the whole flash and writes the factory
  image. Firmware, settings and stored data are removed. Use it for a first install
  or to convert a standalone Meshtastic board to DualBoot.

Boards are not auto-detected: select the exact model and mode yourself. All targets
recheck the live chip family and flash capacity before writing or erasing. DualBoot
updates require a reliably detected capacity and an exact partition-table match;
they never convert layouts in place. T147 NoLoRa has no partition-layout guard:
use Update only over an existing compatible NoLoRa installation. Chip and capacity
checks cannot distinguish different boards with the same chip and flash size.

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

The catalog (`public/data/firmware-catalog.json`) is authenticated with a P-256
signature before the browser uses it. Its verification key is pinned in the web
app; a missing or invalid signature stops the flow. The authenticated catalog pins
every artifact by SHA-256, and each download is checked before a write begins.
This protects catalog and binary integrity, not a compromised web app or hosting
account that can replace the verification code. It does not prevent replay of an
older, validly signed catalog. Wi-Fi OTA updates are delivered
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
regenerate checksums (`python3 scripts/generate_checksums.py`) and sign the catalog
offline. A new guarded layout also needs explicit runtime validation and tests;
adding catalog metadata alone does not implement a new safety guard.

After **any** catalog edit, including formatting:

```bash
npm run sign:catalog -- /private/path/to/catalog-p256-key.pem
npm run verify:catalog
```

The catalog has its own dedicated P-256 key, held apart from the per-device OTA
keys. The signer refuses a key that does not match the pinned public key. Keep
the private key outside this repository and GitHub Actions. CI verifies the
committed signature; it never signs or silently repairs an unsigned catalog.

## Validation and deployment

Pushing to `main` runs the repository validators and test suites — catalog, flash
plans, signed USB catalog, signed OTA release, source privacy, binary-only distribution, checksums,
`npm test` and `npm run build` — then deploys `dist/` to GitHub Pages. A failing
check blocks deployment.

## Licensing

- Web app code (`src/`, `scripts/`, `index.html`) — MIT. See `LICENSE`.
- esptool-js — Apache-2.0, npm dependency.
- Firmware applications — Meshtastic and WadaMesh: GPL-3.0; MeshCore: MIT.
  Only the APE T147 builds (LoRa DualBoot and NoLoRa) carry modified firmware. The
  Heltec V3/V4 builds are upstream Meshtastic and MeshCore plus a small dual-boot
  patch: upstream commit and patch together are the complete source of those builds,
  and both are published — see [`docs/patches/`](docs/patches/). The T147 changes are
  not published; see [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md) for the
  per-target detail.
- APE loaders — separate components distributed as compiled binaries only; their
  implementation source is private.
- Logo and board photography — owner rights reserved.

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
