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

- **Heltec V3** — Meshtastic `8ef996f5b474300c9f06128beff5ce36369f812e`,
  MeshCore `e94125987ed87497e706a0b54d1e80c709343980`
- **Heltec V4** — Meshtastic `cb4efd8f4188303b09795969174d63441633490c`,
  MeshCore `e94125987ed87497e706a0b54d1e80c709343980`
- **APE T147** — WadaMesh `d68f276b0605d4c4da1be93270cbc0d1009fba0d`, Meshtastic
  `8ef996f5b474300c9f06128beff5ce36369f812e` plus the APE T147 changes described
  above. The T147 NoLoRa build comes from the same tree.

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

### Corresponding source

For the GPL-3.0 applications, [sections 1 and 6](https://www.gnu.org/licenses/gpl-3.0.html#section6)
require the corresponding source of the distributed work, including modifications
and the scripts needed to build it. For network distribution, section 6(d) permits
that source on another server with equivalent access and clear directions beside
the binaries.

**Distribution limitation:** this repository publishes the binaries and metadata
only. The upstream commits above are the source of everything APE did not touch,
and they are downloadable from the projects' own repositories. The APE additions
themselves are not published here: neither the T147 changes nor the two dual-boot
additions present in the Heltec V3/V4 builds. The upstream links above identify the
projects; they do not resolve that gap. Publishing only binaries, retaining a
private backup, or adding this notice does not satisfy the corresponding-source
requirement for the modified parts.

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
