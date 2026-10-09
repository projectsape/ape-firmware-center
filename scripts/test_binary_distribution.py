#!/usr/bin/env python3
"""Test the owner-approved binary-only release packaging contract."""
import copy
import importlib
import io
import json
import tarfile
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_ota_release as release_validator


class BinaryOnlyReleaseTests(unittest.TestCase):
    def test_actual_release_accepts_no_source_download_metadata(self):
        with tempfile.TemporaryDirectory(prefix='binary-release-') as folder:
            public = Path(folder) / 'public'
            shutil.copytree(release_validator.ROOT / 'public/firmware/t147-dualboot', public / 'firmware/t147-dualboot')
            catalog = copy.deepcopy(release_validator.load_json(release_validator.ROOT / 'public/data/firmware-catalog.json'))
            device = next(x for x in catalog['devices'] if x['id'] == 't147-lora-dualboot')
            path = public / device['ota']['releaseFile']
            metadata = release_validator.load_json(path)
            metadata.pop('sourceArtifacts', None)
            path.write_text(json.dumps(metadata))
            for component in device['provenance'].values():
                component.pop('sourceArtifact', None)
                component.pop('sourceSha256', None)
            sources = public / 'firmware/t147-dualboot/sources'
            if sources.exists():
                shutil.rmtree(sources)
            try:
                result = release_validator.validate(public, catalog)
            except (KeyError, ValueError) as error:
                self.fail(f'Valid binary-only release was rejected: {error}')
            self.assertTrue(result)


class BinaryDistributionGateTests(unittest.TestCase):
    def test_native_firmware_source_is_rejected(self):
        gate = importlib.import_module('validate_binary_distribution')
        with tempfile.TemporaryDirectory(prefix='binary-native-') as folder:
            root = Path(folder)
            path = root / 'firmware/application.cpp'
            path.parent.mkdir()
            path.write_text('int synthetic_application_source = 1;\n')
            with self.assertRaisesRegex(ValueError, 'source|build'):
                gate.validate(root)

    def test_renamed_archive_is_rejected(self):
        gate = importlib.import_module('validate_binary_distribution')
        with tempfile.TemporaryDirectory(prefix='binary-signature-') as folder:
            root = Path(folder)
            path = root / 'opaque.bin'
            with tarfile.open(path, 'w:gz') as archive:
                payload = b'int synthetic_application_source = 1;\n'
                member = tarfile.TarInfo('application/board.cpp')
                member.size = len(payload)
                archive.addfile(member, io.BytesIO(payload))
            with self.assertRaisesRegex(ValueError, 'archive|source|build'):
                gate.validate(root)

    def test_private_build_metadata_is_rejected(self):
        gate = importlib.import_module('validate_binary_distribution')
        with tempfile.TemporaryDirectory(prefix='binary-metadata-') as folder:
            root = Path(folder)
            path = root / 'release.json'
            path.write_text(json.dumps({'sourceArtifacts': {'app': {'file': 'https://example.invalid/private.dat'}}}))
            with self.assertRaisesRegex(ValueError, 'source|metadata|build'):
                gate.validate(root)

    def test_source_archive_is_rejected(self):
        try:
            gate = importlib.import_module('validate_binary_distribution')
        except ImportError as error:
            self.fail(f'Binary distribution gate is missing: {error}')
        with tempfile.TemporaryDirectory(prefix='binary-policy-') as folder:
            root = Path(folder)
            archive_path = root / 'downloads/source-package.tar.gz'
            archive_path.parent.mkdir()
            with tarfile.open(archive_path, 'w:gz') as archive:
                payload = b'int synthetic_application_source = 1;\n'
                member = tarfile.TarInfo('application/board.cpp')
                member.size = len(payload)
                archive.addfile(member, io.BytesIO(payload))
            with self.assertRaisesRegex(ValueError, 'archive|source|build'):
                gate.validate(root)


if __name__ == '__main__':
    unittest.main()
