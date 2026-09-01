# Third-party licenses and notices

This repository mixes independently-licensed components. The license that
applies depends on which part you are using.

## 1. Web application code — MIT

Everything in `src/`, `scripts/`, `tests/`, `index.html`, and the build tooling
(the Projects APE Flasher web app itself) is licensed under the MIT License.
See `LICENSE`.

## 2. esptool-js — Apache License 2.0

The flasher engine is [esptool-js](https://github.com/espressif/esptool-js),
Copyright Espressif Systems, licensed under the Apache License 2.0. It is an
npm dependency (`esptool-js@^0.6.1`), not vendored source. Redistribution under
Apache-2.0 requires retaining its copyright notice and license text; the full
text is available in the esptool-js repository.

## 3. APE firmware binaries — GPL-3.0

The compiled firmware under `public/firmware/**` is a derivative work of:

- **Meshtastic firmware** — GNU General Public License v3.0 (GPL-3.0).
- **MeshCore** — MIT License, Copyright (c) 2025 Scott Powell / rippleradios.com.

Because Meshtastic is GPL-3.0, the combined APE firmware binaries are
distributed under **GPL-3.0**. Distributing them carries the GPL obligation to
make the corresponding complete source available under GPL-3.0 to anyone who
receives the binaries.

The per-device provenance is:

| Firmware | Upstream(s) | Effective license |
| --- | --- | --- |
| APE DualBoot (Heltec V3/V4) | Meshtastic + MeshCore + APE DualBoot layer | GPL-3.0 |
| APE T147 (LoRa / NoLoRa) | Meshtastic + APE T147 (MUI) patches | GPL-3.0 |

## 4. Brand and product imagery — owner rights reserved

The Projects APE logo and the Heltec / Waveshare board photography retain their
owners' rights and are **not** covered by this repository's MIT license. See
`ASSET_SOURCES.md` for provenance and ownership.
