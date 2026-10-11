# T147 LoRa DualBoot with OTA

Dual-boot firmware for the Waveshare T147 LoRa (ESP32-S3, 1.47" touch LCD). A small
bootloader selects between two radio builds and handles Wi-Fi setup and updates:

- **WadaMesh** — MeshCore-based build (`v1.17.4-touch`).
- **Meshtastic** — standard build (`2.8.1.f7ad9dc`).

Each application keeps its own filesystem and NVS partition, so switching between
them never touches the other's configuration. This repository publishes compiled
firmware and the metadata the web flasher and the OTA feed need — no source packages.

## Current release

### WadaMesh beta_90 — 2026-10-09

The published WadaMesh image is the exact binary flashed and read back on hardware:

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| `wadamesh-08e625cdbfddc46a.bin` — application at `0x1a0000`, served over USB and OTA | 3291728 | `08e625cdbfddc46a1f309f8e62e7a1c776f84ae462afe85841c32e2235dce841` |
| `APE-T147-LoRa-DualBoot-OTA-20261009-afd00ab3ead3b41b.factory.bin` | 16777216 | `afd00ab3ead3b41b282bf45bfa4cb839917fc69537637d847a8a5ee2c0a4f036` |

Firmware identity `v1.17.4-touch`, built from upstream commit `39f342c67e0feaca47ac4302c7d4bda5f399c36d`. The factory
replaces only the WadaMesh slot — every byte outside `0x1a0000`–`0x51ffff` matches the
previous factory — and the USB, OTA and factory paths all deliver the same new bytes.
Earlier immutable artifacts stay published for rollback and for clients holding a
cached manifest.

Meshtastic remains `2.8.1.f7ad9dc` (3,764,096 bytes, SHA256 `abd30fd015aaed5c627814f572912571ed4b42384f351dfd8cfb4058678fdfdf`); its source,
manifests, dependencies and toolchain are untouched. The `Legacy-20261007` loader, the
production public key and the OTA-v2 partition table also remain byte-identical. This
release is `loaderChanged: false`, so a USB update writes both applications — WadaMesh
at `0x1a0000`, Meshtastic at `0x520000` — without a full erase and without touching the
loader, NVS or the filesystems. The two-application validator and the write mechanism
are unchanged, and the test suite exercises both values of the loader flag rather than
relying on the current catalog value.

Verification: host test suite, on-device menu and keyboard checks, USB readback of the
flashed WadaMesh region, and boot logs showing radio, touch and UI up with no fault lines.

### Loader — automatic update checks (`Legacy-20261007`) — 2026-10-07

The current loader checks both applications automatically once Wi-Fi is connected in
OTA; the Check button stays for manual refreshes. Appearance, buttons and the
install/confirm flow are unchanged.

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| `loader-3b44fb49fe56adf2.bin` | 1289104 | `3b44fb49fe56adf2e237ce232eb261dd1a5988d970ff8c9a7e26bd6a04051e61` |

Catalog label `Legacy-20261007`. The matching factory replaces only the loader slot;
everything outside it matches the previous factory. Device testing covered both
automatic HTTPS checks, the manual refresh and the absence of continuous rechecking;
the binary passed flash readback and protected-region comparison. No application was
rebuilt for this release. Only the compiled loader is distributed — its implementation,
ELF images and build snapshots stay outside this repository.

### Identity adoption revision (`Legacy-20261004` r2) — 2026-10-04

A board that received an image by a path other than the loader's own OTA install — the
web flasher writes raw bytes and never touches NVS — now learns the image's official
identity instead of showing `CURRENT: Unknown`. No UI, layout, partition or OTA
behavior changed. Two mechanisms ship in the same binary:

1. After a manifest check whose P-256 signature verified, if the live image matches
   that manifest byte for byte (size + SHA-256) and no identity is stored for it, the
   loader adopts and persists the manifest identity exactly as it does for its own
   OTA installs.
2. The frozen identity table gains the WadaMesh build already in the field
   (3170960 B / `7eda4ac9…`), so those images are named without a network check.

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| `loader-513e11658341700e.bin` | 1288816 | `513e11658341700e87fef6597e7f44318c51e60b811a7996dff240e9900513e6` |
| `APE-T147-LoRa-DualBoot-OTA-20261004-5d905f27074ddbb4.factory.bin` | 16777216 | `5d905f27074ddbb47b8e5cccbc3779bd3aca5f49be9e9c8ca23690413ed54847` |

Only `OtaController.cpp` and `OtaFirmwareIdentity.cpp` differ from the previous
published loader: +320 bytes against the same control build, confined to the DROM and
text segments, with the new identity strings as the only added literals and the same
build recipe. All four host suites (core, identity store, partition, UI) pass. The
production binary was flashed over the guarded USB path — write, readback and
protected-region comparison all pass — and the factory replaces only the loader slot
with erased padding, matching its predecessor everywhere else.

### UI refinement (`Legacy-20261004`) — 2026-10-04

First publication of the Legacy loader. The selector keeps its elongated choices, camo
title and original fonts, without Ready labels; OTA uses larger controls, consistent
Back buttons, balanced application cards, grouped Wi-Fi information and three network
rows with pagination. Only `LoaderUiGeometry.h` and `T147Screen.cpp` differ from the
preceding loader. Host UI tests, actual font metrics, production/bench builds and
physical navigation passed; the production flash passed readback and protected-region
comparison.

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| `loader-fee3a0672e739267.bin` | 1288496 | `fee3a0672e7392678dc082e7e3c428fb5678d2a1ece316c9f625127c97d45265` |
| `APE-T147-LoRa-DualBoot-OTA-20261004-aaad8a439b2b7776.factory.bin` | 16777216 | `aaad8a439b2b77765e867374628c1b1c4f997a3afef26d09ce0e0862f4316b58` |

The factory replaces only the loader slot (`0x20000`–`0x19ffff`) with erased padding;
application binaries, signed manifests, public key, layout and other devices keep their
previous contents. The binary was published exactly as accepted on the board — it was
not rebuilt merely to change its embedded descriptor.

### Retired builds

The standalone LoRa build is no longer offered. It is kept locally only, absent from
the public catalog and download files, and its `0x10000` update must never be reused
for the DualBoot. The public T147 choices are LoRa DualBoot (WadaMesh + Meshtastic +
OTA) and NoLoRa Meshtastic.

## Updating a board

- **USB** — the web flasher writes the catalog's update plan. On a DualBoot board it
  updates WadaMesh and Meshtastic and includes the loader slot only when a release
  marks the loader changed, after verifying 16MB flash and the exact installed OTA-v2
  partition sector. The guard runs before any write, even if session preparation was
  skipped.
- **OTA** — each component has its own `manifest.json` and an immutable SHA-named
  binary. Only one application update/trial may be active at a time; Test and Confirm
  stay manual. Loader self-update is not part of OTA: the loader slot is written only
  by the guarded USB update.
- **Factory** — a fresh installation. It erases previous configuration; use it to
  convert a standalone Meshtastic board to DualBoot.

## Rolling back

The previous immutable artifacts are retained for rollback: `loader-e5b92e8eeda14944.bin`
with `APE-T147-LoRa-DualBoot-OTA-20261003-a9aa2d32eedb4578.factory.bin`, and
`loader-fee3a0672e739267.bin` with `APE-T147-LoRa-DualBoot-OTA-20261004-b9ff1ee74a92069b.factory.bin`.
On a configured OTA-v2 board, restore only the old loader through the guarded USB path —
applications and data survive. Restoring an old factory is a fresh installation and
erases configuration. To roll back the web flasher itself, revert the catalog, release
and checksum changes and redeploy.

## Artifacts and signing

`public/firmware/t147-dualboot/release.json` records firmware paths, sizes, SHA256,
versions, commits and slots. OTA manifests are schema3 with DER P-256 ECDSA/SHA-256
signatures; only the verification public key (`ota-public-key.pem`) is in this
repository, and the signing key stays outside repositories and public files. The
production loader excludes the local test key and the bench USB/LAN interface.

Factory, USB and signed OTA applications must carry identical bytes. The signed display
versions are `v1.17.4-touch` and `2.8.1.f7ad9dc`; frozen application descriptors carry
historical build strings, which are recorded separately as `espAppVersion` instead of
modifying the accepted binaries.

## Production URL

https://projectsape.github.io/ape-firmware-center/firmware/t147-dualboot/update

GitHub Pages serves the built static files; no PC bridge is needed after deployment.
The loader scans Wi-Fi and accepts credentials locally. Its source page is read-only,
the production feed URL is fixed, and only test builds allow changing the feed over
USB — without rewriting stored credentials. A LAN source saved by a test build is
ignored in production.

## Releasing

1. Freeze the approved layout, loader, public verification key and unchanged
   applications. An application-only release reuses its exact accepted bytes; rebuild
   the loader only when a release explicitly calls for it.
2. Stage the matching factory, signed manifests, immutable app files, metadata and
   catalog. For an application-only release, replace the selected slot in the current
   published factory — never reassemble from an older frozen factory — rebuild nothing
   that did not change, and update only that application's USB part and signed manifest.
3. Run the full local pipeline: catalog, flash and OTA validators, rejection tests,
   checksums, `npm test` and `npm run build`.
4. Review the catalog diff and confirm other hardware targets are unchanged.
5. Publish only with explicit approval; a green local run is not authorization to
   deploy.
6. After deployment, re-fetch the public manifests and complete binaries and verify
   signatures, hashes and factory parity. A publication is not permission for another
   device write or factory wipe.
7. The final acceptance test is a real HTTPS application update with manual Test /
   Confirm on a board. Host, USB and local-bridge runs do not replace it.

The deploy workflow runs the release validator, tampering tests, source-privacy and
binary-only distribution gates before building its Pages artifact, then scans the
built `dist/` tree before upload. CI verifies public signatures and never signs with,
or loads, a private key.
