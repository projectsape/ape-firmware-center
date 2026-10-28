# Third-party licenses and credits

## Web application — MIT

The web app itself (`src/`, `scripts/`, `tests/`, `index.html` and the build
tooling) is licensed under the MIT License. See `LICENSE`.

## esptool-js — Apache-2.0

Flasher engine: [esptool-js](https://github.com/espressif/esptool-js), Copyright
Espressif Systems, Apache License 2.0. Used as an npm dependency, not vendored
source.

## Firmware applications

### GPL-3.0 — custom firmware (T147 only)

All boards except the T147 ship official Meshtastic / MeshCore binaries (WadaMesh
only applies to the T147). For those boards there is no modified source to
publish; attribution to the upstream projects is maintained below.

The Waveshare ESP32-S3 Touch 1.47 ("T147") is the exception: it ships a custom
firmware build based on Meshtastic / WadaMesh with substantial own modifications.
The complete corresponding source for that custom T147 build is not currently
published in this repository.

Upstream projects and licenses:

- **Meshtastic** — GPL-3.0 — https://github.com/meshtastic/firmware
- **WadaMesh** — GPL-3.0 — https://github.com/ALLFATHER-BV/wadamesh
- **MeshCore** — MIT, Copyright (c) 2025 Scott Powell / rippleradios.com —
  https://github.com/meshcore-dev/MeshCore

Upstream base commits of the current builds:

- **Heltec V3** — Meshtastic `95ff510f476e238f60c96d0debb355b2fba69449`,
  MeshCore `81dbae592ffad40b4212bc0b37e82b38da08f4bc`
- **Heltec V4** — Meshtastic `eaba8b95bebab04c4f13a27b63e000ebdc1e5fac`,
  MeshCore `81dbae592ffad40b4212bc0b37e82b38da08f4bc`
- **APE T147 LoRa DualBoot** — WadaMesh `0fc1363c61e30c59b8dc4acb7acf4fcb680da56f`,
  Meshtastic `eaba8b95bebab04c4f13a27b63e000ebdc1e5fac` plus the APE T147 changes described above.
- **T147 NoLoRa** — Meshtastic `95ff510f476e238f60c96d0debb355b2fba69449`
  plus the independent APE NoLoRa changes; source availability is unchanged.

#### What the Heltec V3/V4 builds add: dual-boot plumbing, not application changes

Both Heltec builds are upstream Meshtastic and MeshCore. The APE layout only needs
two things from the applications: that they mount their settings from the APE
partition table, and that they hand control back to the APE loader instead of
finalising an OTA reboot. That is all the APE code those binaries carry — about
twenty lines in total, across four files:

- the filesystem partition label in the mount call (`tastic_fs` for Meshtastic,
  `core_fs` for MeshCore);
- a rollback hook (`verifyRollbackLater`) that preserves the pending OTA slot.

Everything else in those builds is build configuration: the APE partition table and
the build flags. No radio, mesh, UI or protocol logic is touched, and neither
application is forked. For scale: the T147 changes described above are 44 files.

These additions are published in [`docs/patches/`](docs/patches/), together with the
partition tables the builds use and the upstream commit each patch applies to.

### Corresponding source

For the GPL-3.0 applications, [sections 1 and 6](https://www.gnu.org/licenses/gpl-3.0.html#section6)
require the corresponding source of the distributed work, including modifications
and the scripts needed to build it. For network distribution, section 6(d) permits
that source on another server with equivalent access and clear directions beside
the binaries.

**Corresponding source per target:**

- **Heltec V3 and Heltec V4 — complete.** The source of those builds is the upstream
  commit listed above plus the APE additions, and both are published: the additions
  and the partition tables they use are in [`docs/patches/`](docs/patches/), each one
  naming the base commit it applies to.
- **APE T147 (LoRa DualBoot and NoLoRa) — not published.** These binaries are
  distributed here with metadata only; the upstream links above identify the projects
  but do not resolve that gap, and this notice does not substitute for the missing
  source.

The **APE loaders** are separate APE firmware components, distributed as compiled
binaries only. Their implementation source is private. They contain no Meshtastic,
WadaMesh or MeshCore code: they are built from APE's own code plus the Arduino
core and the U8g2 library (BSD-2-Clause).

## Brand and product imagery

Not covered by the repository's MIT license:

- **Projects APE logo** — Projects APE. Originals under
  `public/assets/logo/originals/`.
- **Heltec V3/V4 board photography** — Heltec Automation
  ([V3](https://heltec.org/project/wifi-lora-32-v3/),
  [V4](https://heltec.org/project/wifi-lora-32-v4/)). Originals under
  `public/assets/boards/originals/`.
- **T147 board photography** — maintainer-provided photo of the Waveshare
  ESP32-S3-Touch-LCD-1.47
  (https://www.waveshare.com/esp32-s3-touch-lcd-1.47.htm). Trademarks remain with
  Waveshare.
- **Meshtastic device artwork** — not redistributed by this repository.
