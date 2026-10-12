# Third-party licenses and credits

## Web application — MIT

The web app itself (`src/`, `scripts/`, `tests/`, `index.html` and the build
tooling) is licensed under the MIT License. See `LICENSE`.

## esptool-js — Apache-2.0

Flasher engine: [esptool-js](https://github.com/espressif/esptool-js), Copyright
Espressif Systems, Apache License 2.0. Used as an npm dependency, not vendored
source.

## Firmware applications

Compiled firmware keeps its upstream license:

- **Meshtastic** — GPL-3.0 — https://github.com/meshtastic/firmware
- **WadaMesh** — GPL-3.0 — https://github.com/ALLFATHER-BV/wadamesh
- **MeshCore** — MIT, Copyright (c) 2025 Scott Powell / rippleradios.com —
  https://github.com/meshcore-dev/MeshCore

These applications are distributed here as compiled binaries. For the GPL-3.0
applications, [sections 1 and 6](https://www.gnu.org/licenses/gpl-3.0.html#section6)
require the corresponding source for the distributed work, including modifications
and the scripts needed to build it. For network distribution, section 6(d) permits
that source on another server with equivalent access and clear directions beside
the binaries.

**Distribution limitation:** this repository does not currently provide that
complete corresponding source or an exact-source download link for its modified
GPL firmware. The upstream links above identify the projects; they do not resolve
that gap. Publishing only binaries, retaining a private backup, or adding this
notice does not satisfy the corresponding-source requirement.

The **APE loaders** are separate APE firmware components, distributed as compiled
binaries only. Their implementation source is private.

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
