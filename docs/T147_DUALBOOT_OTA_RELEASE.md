# T147 LoRa DualBoot with OTA

## Current application release — WadaMesh beta_90 — 2026-10-09

Owner-authorized publication of the WadaMesh beta_90 integration in the approved
T147 DualBoot port. The exact 3,291,728-byte application already flashed and
readback-verified on the board is reused for USB and signed OTA:
`wadamesh-08e625cdbfddc46a.bin`, SHA256
`08e625cdbfddc46a1f309f8e62e7a1c776f84ae462afe85841c32e2235dce841`.
Its official firmware identity remains `v1.17.4-touch`; the signed upstream
commit is `39f342c67e0feaca47ac4302c7d4bda5f399c36d`. This webflasher distributes
compiled firmware and operational metadata, not firmware source packages.

Meshtastic remains the exact approved `2.8.1.f7ad9dc` application:
3,764,096 bytes, SHA256
`abd30fd015aaed5c627814f572912571ed4b42384f351dfd8cfb4058678fdfdf`.
Its source, signed manifest, dependencies and toolchain are not updated.
The accepted `Legacy-20261007` loader, production public key and OTA-v2
partition table also remain byte-identical. This does not thaw the owner's
Meshtastic compatibility baseline or promote the candidate channel to stable.

The existing USB UPDATE still writes **both applications**, without a full
erase: WadaMesh at `0x1a0000` and Meshtastic at `0x520000`. This release sets
`loaderChanged: false`, so the loader is not written. NVS and filesystems are
outside the application writes. The two-app validator and runtime writing
mechanism are unchanged; tests explicitly exercise both loader-flag values
instead of depending on the current catalog flag.

The matching 16MiB factory is
`APE-T147-LoRa-DualBoot-OTA-20261009-afd00ab3ead3b41b.factory.bin`, SHA256
`afd00ab3ead3b41b282bf45bfa4cb839917fc69537637d847a8a5ee2c0a4f036`.
Only the WadaMesh slot is replaced; every byte outside `0x1a0000` through
`0x51ffff` matches the preceding published factory. All three delivery paths
(USB, OTA and factory) contain the same new WadaMesh bytes. Earlier immutable
artifacts are retained for rollback and cached manifests.

Host tests, T147 menu/keyboard checks, authorized Wada-only USB readback and
boot logs passed. The boot reported radio, touch and UI ready, without fatal
lines. This publication does not perform another device write, factory wipe,
public HTTPS Install/Test/Confirm roundtrip or physical two-app web-USB test.

## Accepted loader — automatic update checks — 2026-10-07

The owner tested and accepted this loader on the T147 and authorized publication.
After connecting to Wi-Fi in OTA, it checks WadaMesh and Meshtastic automatically.
The existing Check button remains available for manual refresh. Appearance,
buttons and application installation/confirmation behavior are unchanged.

The published loader is the exact production binary accepted on the board:
`loader-3b44fb49fe56adf2.bin`, 1,289,104 bytes, SHA256
`3b44fb49fe56adf2e237ce232eb261dd1a5988d970ff8c9a7e26bd6a04051e61`.
Its catalog label is `Legacy-20261007`. The new factory replaces only its loader
slot; every byte outside that slot matches the previous factory. WadaMesh
`v1.17.4-touch` and Meshtastic `2.8.1.f7ad9dc`, their signed manifests, the
partition layout and all other hardware targets retain their existing bytes.
No application firmware was rebuilt or merged for this release.

Host checks passed, and device testing verified both automatic HTTPS checks,
manual refresh and no continuous rechecking. The production loader passed flash
readback and protected-region comparison. Only compiled loader bytes are
distributed; implementation, ELF, build snapshots and private evidence remain
outside this repository. Previous immutable artifacts remain for rollback.

## Publication history

Candidate prepared and publication explicitly approved by the owner 2026-10-03.
The candidate channel remains in place pending the owner's public HTTPS OTA test.
The active T147 choices are LoRa DualBoot (WadaMesh + Meshtastic + OTA) and
NoLoRa Meshtastic. At the owner's request, the earlier standalone LoRa build is
kept locally only and is absent from the public catalog and download files.
Its 0x10000 update is never reused for the DualBoot.

## Primary Legacy loader — 2026-10-04

The owner accepted the visual refinement already installed on the board and
explicitly authorized its GitHub publication as the primary Legacy loader.
`Legacy-20261004` is the release/catalog label for those exact production bytes;
the accepted binary was not rebuilt merely to change its embedded descriptor.

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| USB loader `loader-fee3a0672e739267.bin` | 1288496 | `fee3a0672e7392678dc082e7e3c428fb5678d2a1ece316c9f625127c97d45265` |
| Factory `APE-T147-LoRa-DualBoot-OTA-20261004-aaad8a439b2b7776.factory.bin` | 16777216 | `aaad8a439b2b77765e867374628c1b1c4f997a3afef26d09ce0e0862f4316b58` |

The selector preserves its elongated choices, camo title and original fonts,
without Ready labels. OTA uses larger controls, consistent Back buttons,
balanced application cards, grouped Wi-Fi information and three network rows
with pagination. Only `LoaderUiGeometry.h` and `T147Screen.cpp` differ in runtime
source from the preceding published loader. Host UI tests, actual font metrics,
production/bench builds and physical navigation passed. The final production
flash passed readback and protected-region comparison.

The new factory replaces only the loader slot (0x20000 through 0x19ffff), with
erased padding; every byte outside it matches the previous factory. Application
binaries, signed manifests, public key, layout and other devices retain their
previous contents. The application release remains candidate until a new public
HTTPS Install/Test/Confirm roundtrip is validated; the loader itself is the
accepted Legacy baseline. Source provenance remains `local-uncommitted`: the
implementation checkout has no remote or dedicated source commit, so no loader
source commit is recorded. The loader implementation source is retained
privately and is not published as a source archive.

Keep the previous immutable loaders and factories for rollback:
`loader-e5b92e8eeda14944.bin` with
`APE-T147-LoRa-DualBoot-OTA-20261003-a9aa2d32eedb4578.factory.bin`, and — for the r2
revision below — `loader-fee3a0672e739267.bin` with
`APE-T147-LoRa-DualBoot-OTA-20261004-b9ff1ee74a92069b.factory.bin`.
A configured OTA-v2 board must restore only the old loader through the guarded
USB path, preserving applications and data. Restoring the old factory is a
fresh installation that erases configuration. For the webflasher baseline,
revert this publication's catalog/release/checksum changes and deploy only with
explicit owner approval; retain both generations of immutable artifacts.

## Primary Legacy loader r2 — USB identity adoption — 2026-10-04

Owner-authorized revision of the accepted Legacy loader. It changes no UI, layout,
partition or OTA behavior. A device that received a published image by a path other
than the loader's own OTA install — the web flasher writes raw bytes and never touches
NVS — now learns that image's official identity instead of showing `CURRENT: Unknown`.
Two mechanisms ship together in the same binary:

1. After a manifest check whose P-256 signature already verified, when the live image
   matches that manifest byte for byte (size + SHA-256) and the loader holds no stored
   identity for it, the loader adopts and persists the manifest identity exactly as it
   does for its own OTA installs.
2. The frozen identity table gains the currently published WadaMesh pair
   (3170960 B / `7eda4ac9…`) so images already in the field are named without a check.

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| USB loader `loader-513e11658341700e.bin` | 1288816 | `513e11658341700e87fef6597e7f44318c51e60b811a7996dff240e9900513e6` |
| Factory `APE-T147-LoRa-DualBoot-OTA-20261004-5d905f27074ddbb4.factory.bin` | 16777216 | `5d905f27074ddbb47b8e5cccbc3779bd3aca5f49be9e9c8ca23690413ed54847` |

Only `loader/src/OtaController.cpp` and `loader/src/OtaFirmwareIdentity.cpp` differ from
the preceding published loader: +320 bytes against the same control build, confined to
the DROM and text segments, with the new identity strings as the only added literals and
the same build recipe. All four host suites (core, identity store, partition, UI) pass.
The production binary was flashed over the guarded USB path
(`scripts/replace_loader_local.py`: write, readback and protected-region comparison
PASS); the new factory replaces only the loader slot with erased padding and is
otherwise byte-identical to its predecessor.

## Artifacts and trust

The full factory image is 16MiB, assembled from the accepted blank-configuration
Legacy factory plus the reviewed OTA-v2 layout and production HTTPS loader.
It is for a fresh installation and erases previous configuration. Existing
OTA-v2 boards can update WadaMesh, Meshtastic and — when a release marks the
loader changed — the loader at 0x20000, without a full erase, after exact
partition-sector comparison at 0x8000 and reliable 16MB flash detection.
The guard runs before any write even if session preparation was skipped.

`public/firmware/t147-dualboot/release.json` records firmware paths, sizes,
SHA256, versions, commits and slots. No firmware source packages are included.
The independent loader source is private. OTA
manifests are schema3 with DER P-256 ECDSA/SHA256 signatures. Only the
verification public PEM is in this repository. The private signing key stays
outside repositories and must never be added to public files or workflow logs.
The local test key and bench USB/LAN interface are excluded from the production
loader.

Factory, USB and signed OTA applications must use the same bytes. The
signed display versions are v1.17.4-touch and 2.8.1.f7ad9dc. Frozen app ESP
descriptors carry historical build strings; those are recorded separately as
espAppVersion rather than changing the accepted application binaries.

## Production URL

https://projectsape.github.io/ape-firmware-center/firmware/t147-dualboot/update

Each component has its own manifest.json and an immutable SHA-named bin:
update/wadamesh/ and update/meshtastic/. Keep previous hash-named binaries when
updating the stable manifests; cached older manifests can still resolve their
original package. GitHub Pages serves the built static files; no PC bridge is
needed after deployment. The loader scans Wi-Fi and accepts credentials locally.
Source is a view-only page. Production ignores any previously saved LAN source
without rewriting credentials. Only test builds permit feed changes by USB.

Only one app update/trial may be active. Test and Confirm remain manual. Apps
can also be installed from the web flasher over USB. Loader self-update is not
OTA: the loader slot is included in the guarded USB update only when a release
marks it changed.

## Preparing and approving a release

1. Freeze the approved layout, loader, public verification key and unchanged
   applications. Rebuild the loader only when separately requested; an
   application-only release reuses its exact accepted bytes.
2. Stage the matching factory, signed app manifests, immutable app files,
   operational metadata and catalog. Keep firmware source packages, build
   evidence and the owner-only private key outside the repo.
   The initial frozen-release builder is prepare_web_release.py in the T147
   loader project. Future app-only releases replace the selected slot in the
   current published factory, update that app's USB part and signed manifest,
   and retain the other app. Do not reassemble from an older frozen factory,
   rebuild unchanged applications, or make a version-label-only change.
3. Run all catalog/flash/OTA/checksum checks, rejection tests, npm test and build.
4. Review the catalog diff and UI. Confirm other hardware targets are unchanged.
5. Obtain explicit owner approval for commit/push/Pages publication. Local tests
   or prior visual approval do not authorize remote publication.
6. After authorized deployment, fetch both public manifests and complete bins,
   verify signatures/hashes, factory parity and the unchanged components. A
   publication is not permission for another device write or factory wipe.
7. Validate an actual HTTPS app update with the owner, including manual Test /
   Confirm. Host/USB/local-bridge tests do not replace this final public test.

The deploy workflow runs the release validator, tampering tests, source privacy
and binary-only distribution gates before building its Pages artifact, then
scans the built `dist/`
tree before upload. CI verifies public signatures, never signs with or loads a
private key. The existing push-main deployment trigger is unchanged.
