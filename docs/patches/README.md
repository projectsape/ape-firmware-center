# APE dual-boot patches — Heltec V3 and Heltec V4

These patches are the complete APE additions compiled into the Heltec V3 and Heltec
V4 firmware binaries published by this flasher. Applying one of them to the upstream
commit it names reproduces **exactly** the source the released binary was built
from: every other file in those builds is upstream, unmodified.

| Patch | Upstream project | Base commit |
| --- | --- | --- |
| `heltec-v3-meshtastic-dualboot.patch` | [meshtastic/firmware](https://github.com/meshtastic/firmware) | `95ff510f476e238f60c96d0debb355b2fba69449` |
| `heltec-v3-meshcore-dualboot.patch` | [meshcore-dev/MeshCore](https://github.com/meshcore-dev/MeshCore) | `81dbae592ffad40b4212bc0b37e82b38da08f4bc` |
| `heltec-v4-meshtastic-dualboot.patch` | [meshtastic/firmware](https://github.com/meshtastic/firmware) | `eaba8b95bebab04c4f13a27b63e000ebdc1e5fac` |
| `heltec-v4-meshcore-dualboot.patch` | [meshcore-dev/MeshCore](https://github.com/meshcore-dev/MeshCore) | `81dbae592ffad40b4212bc0b37e82b38da08f4bc` |

What the patches do — and nothing else:

- mount the application filesystem from the APE partition table instead of the
  default partition scan (`tastic_fs` for Meshtastic, `core_fs` for MeshCore), so
  settings live in the APE layout;
- add the `verifyRollbackLater()` hook, which keeps the pending OTA slot so a
  restarted application returns to the APE loader;
- point the build at the APE partition table and define the dual-boot build flag.

No radio, mesh, UI or protocol code is touched, and neither project is forked.

## Reproducing a build

The variant files reference `../partitions/<name>-build.csv`, so lay the tree out the
way the build expects:

```
build/
├── firmware/                     # upstream at the base commit, patch applied
└── partitions/
    ├── meshtastic-build.csv      # or meshcore-build.csv
    └── ...
```

Copy the CSVs from `partitions/` here under those names, then build the environment
the patch edits: `heltec-v3` or `heltec-v4` for Meshtastic,
`Heltec_v3_companion_radio_ble` or `heltec_v4_companion_radio_ble` for MeshCore.

The Heltec V4 Meshtastic patch adds `partitions.csv` at the tree root, which is the
table that build uses; no external CSV is needed for it.

## Verifying a patch

```sh
git clone https://github.com/meshtastic/firmware && cd firmware
git checkout 95ff510f476e238f60c96d0debb355b2fba69449
git apply --whitespace=nowarn ../heltec-v3-meshtastic-dualboot.patch
```

`git apply` reports a whitespace warning for the trailing-newline fix in
`FSCommon.h`; the patch applies as-is. The same procedure works for each patch with
its own repository and base commit.

## Not covered here

The APE T147 builds (LoRa DualBoot and NoLoRa) carry substantial APE changes and are
**not** published. The APE loaders are APE's own components and contain no
Meshtastic, WadaMesh or MeshCore code.
