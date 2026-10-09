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

## 3. APE firmware components — component-specific terms

The firmware collection contains distinct application and loader components;
licensing and source availability are described per component:

- **Meshtastic application builds** — GNU General Public License v3.0
  (GPL-3.0).
- **WadaMesh application builds** — GPL-3.0.
- **MeshCore components** — MIT License, Copyright (c) 2025 Scott Powell /
  rippleradios.com.
- **APE T147 loader** — a separate firmware component. Its implementation
  source is retained privately. The catalog records its version and factual
  local source state without publishing source or inventing a source commit.

Distributing a GPL-licensed application carries the corresponding-source
obligations that apply to that application. This webflasher serves compiled
firmware and operational metadata, not firmware source packages; this packaging
policy does not remove those obligations or constitute a claim that they have
been fulfilled. The loader's presence alongside
those applications does not, by itself, determine the loader source's license.
This repository does not offer the private loader implementation source under
GPL. These descriptions document component and source boundaries; they do not
purport to revoke or change rights granted by any applicable license.

## 4. Brand and product imagery — owner rights reserved

The Projects APE logo and the Heltec / Waveshare board photography retain their
owners' rights and are **not** covered by this repository's MIT license. See
`ASSET_SOURCES.md` for provenance and ownership.
