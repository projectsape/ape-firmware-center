# Firmware releases

This repository publishes compiled firmware and the metadata the flasher needs.
Every artifact is pinned by SHA-256 in the catalog and verified before any write.
Here are the current releases per device and the history of what has been
published.

Each device carries a catalog channel: `stable` for a round the owner has
validated on hardware end to end, `candidate` for a freshly published round that
is still awaiting that pass.

## Waveshare T147 LoRa DualBoot — WadaMesh + Meshtastic + OTA

Release: **2026-10-11** · catalog channel: **stable**.
WadaMesh `v1.17.4-touch`; Meshtastic `2.8.2.18ec962`; Loader `Legacy-20261007`.

| Artifact | Slot | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `wadamesh-7f461cb1e46ef88d.bin` | `0x1a0000` | 3384720 | `7f461cb1e46ef88d824a2406190c4ec22da0b8819e072b93f95952ebb7343f81` |
| `meshtastic-50e45bfec976f29e.bin` | `0x520000` | 3754608 | `50e45bfec976f29ea15b4ed1d527a0515af53f4dfe423e7644c5837fc7be7876` |
| `partitions-ota-v2.bin` | `0x8000` | 4096 | `c7e60fcb1a19ecb84df674a908c8e48744e3f5fb8a81fa19fb4f341b07db4cfa` |
| `loader-3b44fb49fe56adf2.bin` | `0x20000` | 1289104 | `3b44fb49fe56adf2e237ce232eb261dd1a5988d970ff8c9a7e26bd6a04051e61` |
| `APE-T147-LoRa-DualBoot-OTA-20261011-2b5a39c9cd85baa0.factory.bin` | `0x0` | 16777216 | `2b5a39c9cd85baa085bdb927b07f8e6ff5218700ed9eaaa5b481aa9e84a5009d` |

- USB Update writes WadaMesh and Meshtastic. The loader is unchanged.
- Layout `ape-t147-dualboot-ota-v2`; the installed partition sector is checked before each USB update.
- The signed Wi-Fi OTA feed remains available from the loader menu.
  Feed: `https://projectsape.github.io/ape-firmware-center/firmware/t147-dualboot/update`
  — one operation at a time, manual Test and Confirm.

## Waveshare T147 NoLoRa — Meshtastic

Release: **2026-10-11** · catalog channel: **stable**.
Meshtastic `2.8.2`.

| Artifact | Slot | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `meshtastic-8ed009f8a31b73ce.bin` | `0x10000` | 3719424 | `8ed009f8a31b73ceeb0b0b0185d50f060c7c53d36e821b55f41b2edc5a8cc0a2` |
| `T147-NoLoRa-20261011-c53d54aa091a1c89.factory.bin` | `0x0` | 3784960 | `c53d54aa091a1c8900ba4aea16de9b5967b2733cc0f0b1866110ed6c49ef2820` |
| `T147-NoLoRa.littlefs.bin` | `0xC90000` | 3538944 | `2025b200ef42e636a5258f8db9f734a855dfb91a8a36c3c2bbdc5ea2f0ce92c6` |

- USB Update writes the application at `0x10000`, preserving NVS and the filesystem.
- This target has no partition-table guard. Update requires an existing compatible NoLoRa installation; chip and flash capacity alone do not prove the installed layout.

## Heltec V4 DualBoot with OTA

Release: **2026-10-11** · catalog channel: **stable**.
MeshCore `v1.17.1`; Meshtastic `2.8.2.2a8d5a2`; Loader `UIv4.5c-20261010`.

| Artifact | Slot | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `meshcore-8c540a54da6e2991.bin` | `0x1a0000` | 1270480 | `8c540a54da6e2991f7a26260e2031bc15788662989f2e4d5ac0d43fa773309f1` |
| `meshtastic-58d5aa7b98a14afc.bin` | `0x3a0000` | 2288320 | `58d5aa7b98a14afc7aaa0dcc7b1a084402454ed67954c178eee2681535e0b532` |
| `partitions-ota-v1.bin` | `0x8000` | 4096 | `23353614a32bd5d4213e986be966c09076ba94232b740097d2f9089f89779ba1` |
| `loader-2aa4b3da757219c3.bin` | `0x20000` | 1012048 | `2aa4b3da757219c312033fad2d9072c7e1af197d7780bfe2dc8f2eb9a8e62d75` |
| `APE-Heltec-V4-DualBoot-OTA-20261011-1e97abcfa151ae04.factory.bin` | `0x0` | 16777216 | `1e97abcfa151ae04070bcfd6bb140248320bcdc1bccc27e0ea39991ac4edd8cf` |

- USB Update writes MeshCore and Meshtastic. The loader is unchanged.
- Layout `ape-heltec-v4-dualboot-ota-v1`; the installed partition sector is checked before each USB update.
- The signed Wi-Fi OTA feed remains available from the loader menu.
  Feed: `https://projectsape.github.io/ape-firmware-center/firmware/heltec-v4/update`
  with schema-3 P-256 manifests. The loader pins the feed URL, embeds the public
  key and verifies TLS against the ISRG roots (X1/X2) — no plain HTTP, no fallback.

| partition | type | offset | size |
| --- | --- | --- | --- |
| nvs | data/nvs | 0x009000 | 0x006000 |
| otadata | data/ota | 0x00f000 | 0x002000 |
| loader_nvs | data/nvs | 0x011000 | 0x00f000 |
| loader | app/factory | 0x020000 | 0x180000 |
| meshcore | app/ota_0 | 0x1a0000 | 0x200000 |
| meshtas | app/ota_1 | 0x3a0000 | 0x300000 |
| core_fs | data/spiffs | 0x6a0000 | 0x4b0000 |
| tastic_fs | data/spiffs | 0xb50000 | 0x4b0000 |

## Heltec V3 DualBoot

Release: **2026-10-11** · catalog channel: **stable**.
Meshtastic `2.8.2`; MeshCore `1.17.1`; Loader `1.0.0`.

| Artifact | Slot | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `meshcore-3441d3e9b1018203.bin` | `0xA0000` | 1272800 | `3441d3e9b10182031b9b2a8cfb2849b95a2316d19cbcf7f249513d7613828fd3` |
| `meshtastic-33be06ef07863650.bin` | `0x300000` | 2269808 | `33be06ef0786365058ab4f32092b3d66155f390c8882a0a386087e88b80825f2` |
| `partitions-dualboot-8mb-v1.bin` | `0x8000` | 4096 | `136629b9345e7d6eec5352c12f20097c15d6f809852ecb629586ae0537517fde` |
| `loader.bin` | `0x20000` | 290976 | `3ba56a44e1d78c790f3850a4f99f82987fcec5789a68bc4e357b7353790b9bf4` |
| `APE-Heltec-V3-DualBoot-8MB-20261011-418551b6f15453fe.factory.bin` | `0x0` | 8388608 | `418551b6f15453fe94cc3079e113c7916a1d595e6e6b5f40fb176a9ed7d777af` |

- USB Update writes MeshCore and Meshtastic. The loader is unchanged.
- The web guard `ape-heltec-v3-dualboot-8mb-v1` names the existing production 8MB table; it does not introduce a new on-device layout.
- Its reference is the exact 4096-byte sector at `0x8000` in the published factory. It contains loader `0x20000` / `0x80000` bytes, MeshCore `0xa0000` / `0x260000`, Meshtastic `0x300000` / `0x260000`, core_fs `0x560000` / `0x150000` and tastic_fs `0x6b0000` / `0x150000`.
- The table is compared during preparation and again at the write boundary; an unknown capacity, unreadable table or mismatching layout stops the update without erasing or writing.

## Signing and integrity

- The USB catalog is accompanied by `data/firmware-catalog.sig.json`. WebCrypto
  checks its ECDSA P-256/SHA-256 signature before the catalog is parsed or used.
  The public key is pinned in `src/catalog-signature.js` and is a key dedicated to
  the catalog, held apart from the per-device OTA keys so each anchor rotates on
  its own. No private key is shipped or stored in CI.
- The signed payload is the UTF-8 prefix `APE-FIRMWARE-CATALOG-V1\n` followed by
  the exact catalog file bytes. The signature uses base64-encoded raw `r || s`
  (64 bytes / IEEE P1363), not DER. Reformatting the JSON requires a new signature.
- This authenticates metadata against the bundled key, then SHA-256 authenticates
  each binary against that metadata. It is not protection against replacement of
  the web app itself and does not reject an older, correctly signed catalog.
- OTA manifests are schema 3 with DER P-256 ECDSA/SHA-256 signatures. The
  verification public key (`ota-public-key.pem`) is published per device; the
  private signing key is not in this repository.
- Only compiled binaries and operational metadata are published — firmware source
  is not hosted here. Third-party licenses: see `THIRD_PARTY_LICENSES.md`.

## Updating and rollback

- **UPDATE** writes the declared update partitions and never erases. **CLEAN
  INSTALL** erases the whole flash and writes the factory image.
- The loader slot is USB-only, written only when a release marks the loader
  changed; OTA never rewrites it.
- Previous immutable artifacts remain in the repository history. A USB rollback
  release must retain the installed layout, supply both applications and set
  `loaderChanged: true` if restoring the loader. Update is not a loader-only mode.
  Restoring an older factory is a clean install and erases configuration.

## Previous releases

T147 LoRa DualBoot:

- `Legacy-20261004` r2 — an image installed by the web flasher (raw bytes, no NVS
  write) now adopts its manifest identity instead of showing `CURRENT: Unknown`
  (`loader-513e1165…`, factory `…5d905f27…`).
- `Legacy-20261004` — selector UI refinement: elongated choices, camo title,
  larger OTA controls, pagination; no Ready labels (`loader-fee3a067…`, factory
  `…aaad8a43…`).
- `Legacy-20261003` — first Legacy publication (`loader-e5b92e8e…`, factory
  `…a9aa2d32…`).

Heltec V4:

- `UIv4.5c-20261010` — BACK is serviced before automatic OTA work; CANCEL while
  busy, BACK when idle, and cancelled exit does not relaunch a check. The loop-task
  stack is 16 KiB so entering OTA cannot trip the stack canary.
- `UIv4.4` — fixes the selector countdown expiring the instant BACK was pressed in
  OTA (an unsigned `millis()` underflow; signed deltas now, as in the T147).
- `UIv4.2` / `UIv4.3` — leaving OTA re-arms a fresh five-second countdown for the
  last application, surviving a residual button hold.
- `UIv4.1` — application cards simplified; the update check runs automatically.

## Publishing a release

1. Freeze the layout, loader, public key and unchanged applications; an
   application-only release reuses its exact accepted bytes.
2. Stage the factory, signed manifests, immutable binaries, metadata and catalog.
   For an application-only release, replace the slot in the current published
   factory — never reassemble from an older one — and update only that
   application's USB part and manifest.
3. Sign the finished catalog offline with
   `npm run sign:catalog -- /private/path/to/catalog-p256-key.pem`.
   Run all gates in `.github/workflows/deploy.yml`, including
   `npm run verify:catalog`, the flash-plan and OTA validators, rejection tests,
   checksums, `npm test`, `npm run build`, and signature/privacy/binary-only checks
   over `dist/`. Signing is never an automatic CI step.
4. Review the catalog diff; confirm other devices are unchanged.
5. Publish only with explicit approval; a green local run is not authorization.
6. After deployment, re-fetch the public catalog, catalog signature and OTA
   manifests; verify signatures, hashes and factory parity.
7. Acceptance test: a real HTTPS update with manual Test/Confirm on a board.
