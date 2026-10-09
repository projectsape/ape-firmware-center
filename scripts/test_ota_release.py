#!/usr/bin/env python3
"""Tamper actual staged packages: every fixture must fail before publication."""
import base64
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import validate_ota_release as v


class ReleaseRejections(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.public = Path(self.directory.name) / 'public'
        shutil.copytree(v.ROOT / 'public/firmware/t147-dualboot', self.public / 'firmware/t147-dualboot')
        self.catalog = v.load_json(v.ROOT / 'public/data/firmware-catalog.json')
        self.device = next(x for x in self.catalog['devices'] if x['id'] == 't147-lora-dualboot')
        self.release_path = self.public / self.device['ota']['releaseFile']
        self.release = v.load_json(self.release_path)
        self.manifest_path = self.public / self.release['components']['wadamesh']['manifest']
        self.manifest = v.load_json(self.manifest_path)

    def tearDown(self):
        self.directory.cleanup()

    def save_manifest(self):
        self.manifest_path.write_text(json.dumps(self.manifest))

    def save_release(self):
        self.release_path.write_text(json.dumps(self.release))

    def reject(self):
        with self.assertRaises((ValueError, KeyError, TypeError)):
            v.validate(self.public, self.catalog)

    def test_actual_release_passes(self):
        self.assertTrue(v.validate(self.public, self.catalog))

    def test_release_passes_without_public_firmware_sources(self):
        self.assertNotIn('sourceArtifacts', self.release)
        self.assertEqual(
            list((self.public / 'firmware/t147-dualboot').rglob('*.tar*')), []
        )
        for provenance in self.device['provenance'].values():
            self.assertNotIn('sourceArtifact', provenance)
            self.assertNotIn('sourceSha256', provenance)
        self.assertTrue(v.validate(self.public, self.catalog))

    def test_release_rejects_firmware_source_artifact_entries(self):
        for component in ('loader', 'wadamesh', 'meshtastic'):
            with self.subTest(component=component):
                self.release['sourceArtifacts'] = {component: {
                    'file': 'firmware/private.tar.gz',
                    'bytes': 1,
                    'sha256': '0' * 64,
                }}
                self.save_release()
                self.reject()

    def test_bad_signature(self):
        signature = bytearray(base64.b64decode(self.manifest['signature']))
        signature[-1] ^= 1
        self.manifest['signature'] = base64.b64encode(signature).decode()
        self.save_manifest()
        self.reject()

    def test_altered_signed_commit(self):
        self.manifest['commit'] = '0' * 40
        self.save_manifest()
        self.reject()

    def test_oversize_app(self):
        self.manifest['size'] = 0x380001
        self.save_manifest()
        self.reject()

    def test_external_firmware_url(self):
        self.manifest['firmware_url'] = 'https://example.com/firmware.bin'
        self.save_manifest()
        self.reject()

    def test_path_traversal(self):
        self.manifest['firmware_url'] = '../meshtastic/firmware.bin'
        self.save_manifest()
        self.reject()

    def test_test_version(self):
        self.manifest['app_version'] = 'Legacy-TEST'
        self.save_manifest()
        self.reject()

    def test_untrusted_manifest_field(self):
        self.manifest['surprise'] = 'ignored?'
        self.save_manifest()
        self.reject()

    def test_duplicate_json_field(self):
        raw = json.dumps(self.manifest)
        self.manifest_path.write_text(raw[:-1] + ',"component":"wadamesh"}')
        self.reject()

    def test_app_bytes_changed(self):
        path = self.public / self.release['components']['wadamesh']['file']
        data = bytearray(path.read_bytes())
        data[64] ^= 1
        path.write_bytes(data)
        self.reject()

    def test_factory_app_diff_even_if_factory_hashes_updated(self):
        info = self.release['factory']
        path = self.public / info['file']
        data = bytearray(path.read_bytes())
        data[0x1a0000 + 64] ^= 1
        path.write_bytes(data)
        info['sha256'] = v.sha(data)
        self.device['factory']['parts'][0]['sha256'] = info['sha256']
        self.save_release()
        self.reject()

    def test_lan_feed(self):
        self.device['ota']['feedUrl'] = 'http://192.168.1.169:8767/firmware/t147-dualboot/update'
        self.reject()

    def test_unsafe_usb_offset(self):
        self.device['update']['parts'][0]['offset'] = '0x10000'
        self.reject()

    def test_usb_app_part_removed(self):
        self.device['update']['parts'] = [p for p in self.device['update']['parts'] if p['name'] != 'meshtastic']
        self.reject()

    def test_usb_unknown_part(self):
        self.device['update']['parts'].append({
            'name': 'extra',
            'file': 'firmware/t147-dualboot/update/partitions-ota-v2.bin',
            'sha256': '0' * 64,
            'offset': '0x900000',
        })
        self.reject()

    def test_usb_app_sha_mismatch(self):
        next(p for p in self.device['update']['parts'] if p['name'] == 'wadamesh')['sha256'] = '0' * 64
        self.reject()

    def test_usb_loader_unchanged_flag_accepted(self):
        self.device['update']['loaderChanged'] = False
        self.assertTrue(v.validate(self.public, self.catalog))

    def test_usb_loader_changed_requires_metadata(self):
        self.device['update']['loaderChanged'] = True
        del self.device['loader']
        self.reject()

    def test_usb_loader_changed_flag_accepted(self):
        self.device['update']['loaderChanged'] = True
        self.assertTrue(v.validate(self.public, self.catalog))

    def test_usb_loader_offset(self):
        self.device['loader']['offset'] = '0x10000'
        self.reject()

    def test_usb_loader_metadata_mismatch(self):
        self.device['loader']['sha256'] = '0' * 64
        self.reject()

    def test_guard_removed(self):
        del self.device['update']['requiredLayout']
        self.reject()

    def test_unknown_flash_allowed(self):
        self.device['update']['requireVerifiedFlashSize'] = False
        self.reject()

    def test_bench_release(self):
        self.release['loader']['bench'] = True
        self.save_release()
        self.reject()

    def test_test_key_metadata(self):
        self.release['publicKey']['testKeySha256'] = self.release['publicKey']['sha256']
        self.save_release()
        self.reject()

    def test_standalone_lora_exposed(self):
        self.catalog['archivedDevices'] = [{'id': 't147-lora'}]
        self.reject()


if __name__ == '__main__':
    unittest.main()
