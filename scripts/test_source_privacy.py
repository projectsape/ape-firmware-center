#!/usr/bin/env python3
"""Regression tests for source privacy checks on public and built site trees."""
import bz2
import gzip
import hashlib
import io
import json
import lzma
import shutil
import stat
import struct
import tarfile
import tempfile
import time
import unittest
import zipfile
import zlib
from pathlib import Path
from unittest import mock

import validate_source_privacy as privacy


class SourcePrivacyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='source-privacy-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'site'
        (self.root / 'firmware').mkdir(parents=True)

    def write_json(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        return path

    def write_tar(self, path, entries):
        path.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(path, 'w:gz') as archive:
            for name, kind, payload in entries:
                info = tarfile.TarInfo(name)
                if kind == 'file':
                    info.size = len(payload)
                    archive.addfile(info, io.BytesIO(payload))
                else:
                    info.type = tarfile.SYMTYPE
                    info.linkname = payload.decode()
                    archive.addfile(info)

    @staticmethod
    def tar_header(name, size, kind=b'0', ustar=True):
        header = bytearray(512)
        header[:len(name)] = name.encode('utf-8')
        header[100:108] = b'0000644\0'
        header[108:116] = b'0000000\0'
        header[116:124] = b'0000000\0'
        header[124:136] = f'{size:011o}\0'.encode('ascii')
        header[136:148] = b'00000000000\0'
        header[148:156] = b'        '
        header[156:157] = kind
        if ustar:
            header[257:263] = b'ustar\0'
            header[263:265] = b'00'
        checksum = sum(header)
        header[148:156] = f'{checksum:06o}\0 '.encode('ascii')
        return bytes(header)

    @staticmethod
    def pax_record(key, value):
        body = f' {key}={value}\n'.encode('utf-8')
        length = len(body) + 1
        while True:
            record = str(length).encode('ascii') + body
            if len(record) == length:
                return record
            length = len(record)

    @classmethod
    def raw_tar(cls, entries):
        result = bytearray()
        for name, kind, payload in entries:
            result.extend(cls.tar_header(name, len(payload), kind))
            result.extend(payload)
            result.extend(b'\0' * ((-len(payload)) % 512))
        result.extend(b'\0' * 1024)
        return bytes(result)

    def nested_tar(self, depth, leaf_entries):
        data = self.raw_tar(leaf_entries)
        for index in range(depth):
            data = self.raw_tar([(f'inner-{index}.dat', b'0', data)])
        return data

    @staticmethod
    def loader_layout_entries():
        entries = []
        for index in range(7):
            entries.append((f'loader/include/part{index}.h', 'file', b'#pragma once\n'))
            entries.append((f'loader/src/part{index}.cpp', 'file', b'int part() { return 0; }\n'))
        return entries

    def test_expected_public_binary_tree_passes(self):
        privacy.validate_site(privacy.ROOT / 'public')

    def test_allowed_app_source_archives_are_not_false_positives(self):
        # Test the generic privacy scanner in isolation using synthetic fixtures.
        # The separate binary-distribution gate forbids all archives on the site.
        for name in ('synthetic-app-one.tar.gz', 'synthetic-app-two.tar.gz'):
            self.write_tar(self.root / 'firmware' / name, [
                ('application/runtime.cpp', 'file', b'int synthetic_application = 1;\n'),
            ])
        privacy.validate_site(self.root)

    def test_tar_source_is_rejected_under_an_alternate_filename(self):
        archive = self.root / 'firmware/opaque-package.bin'
        self.write_tar(archive, self.loader_layout_entries())
        with self.assertRaises(privacy.PrivacyViolation):
            privacy.validate_site(self.root)

    def test_archive_source_fingerprint_is_detected_after_member_renaming(self):
        payload = b'synthetic private source fingerprint fixture\n'
        archive = self.root / 'firmware/opaque-package.bin'
        self.write_tar(archive, [('vendor/components/renamed.data', 'file', payload)])
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {hashlib.sha256(payload).hexdigest()}):
            with self.assertRaises(privacy.PrivacyViolation):
                privacy.validate_site(self.root)

    def test_fingerprint_and_loader_path_are_checked_outside_firmware(self):
        (self.root / 'firmware').rmdir()
        payload = b'synthetic private source fingerprint fixture\n'
        path = self.root / 'downloads/assets/opaque.dat'
        path.parent.mkdir(parents=True)
        path.write_bytes(payload)
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {hashlib.sha256(payload).hexdigest()}):
            with self.assertRaisesRegex(privacy.PrivacyViolation, 'fingerprint'):
                privacy.validate_site(self.root)

        path.unlink()
        path = self.root / 'downloads/loader/src/implementation.cpp'
        path.parent.mkdir(parents=True)
        path.write_text('int synthetic_loader_source;\n')
        with self.assertRaisesRegex(privacy.PrivacyViolation, 'loader source'):
            privacy.validate_site(self.root)

    def test_fingerprint_scan_covers_bounded_larger_opaque_files(self):
        payload = b'synthetic fixture:' + b'x' * (1024 * 1024)
        path = self.root / 'downloads/assets/large-opaque.dat'
        path.parent.mkdir(parents=True)
        path.write_bytes(payload)
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {hashlib.sha256(payload).hexdigest()}):
            with self.assertRaisesRegex(privacy.PrivacyViolation, 'fingerprint'):
                privacy.validate_site(self.root)

    def test_nested_tar_and_zip_archives_are_inspected(self):
        payload = b'synthetic private source fingerprint fixture\n'
        inner = self.raw_tar([('renamed.dat', b'0', payload)])
        outer_tar = self.root / 'firmware/outer.tar'
        self.write_tar(outer_tar, [('bundles/inner.dat', 'file', inner)])
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {hashlib.sha256(payload).hexdigest()}):
            with self.assertRaisesRegex(privacy.PrivacyViolation, 'fingerprint|nested archive'):
                privacy.validate_site(self.root)

        outer_tar.unlink()
        outer_zip = self.root / 'firmware/outer.zip'
        with zipfile.ZipFile(outer_zip, 'w') as output:
            output.writestr('bundles/inner.dat', inner)
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {hashlib.sha256(payload).hexdigest()}):
            with self.assertRaisesRegex(privacy.PrivacyViolation, 'fingerprint|nested archive'):
                privacy.validate_site(self.root)

        outer_zip.unlink()
        inner_zip_stream = io.BytesIO()
        with zipfile.ZipFile(inner_zip_stream, 'w') as output:
            output.writestr('renamed.data', payload)
        inner_zip = inner_zip_stream.getvalue()
        outer_tar = self.root / 'firmware/outer-with-zip.tar.gz'
        self.write_tar(outer_tar, [('bundles/inner.data', 'file', inner_zip)])
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {hashlib.sha256(payload).hexdigest()}):
            with self.assertRaisesRegex(privacy.PrivacyViolation, 'fingerprint|nested archive'):
                privacy.validate_site(self.root)

        outer_tar.unlink()
        outer_zip = self.root / 'firmware/outer-with-zip.zip'
        with zipfile.ZipFile(outer_zip, 'w') as output:
            output.writestr('bundles/inner.data', inner_zip)
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {hashlib.sha256(payload).hexdigest()}):
            with self.assertRaisesRegex(privacy.PrivacyViolation, 'fingerprint|nested archive'):
                privacy.validate_site(self.root)

    def test_nested_archive_depth_is_bounded(self):
        nested = self.nested_tar(8, [('leaf.txt', b'0', b'benign')])
        path = self.root / 'firmware/nested.tar'
        path.write_bytes(nested)
        with self.assertRaisesRegex(privacy.PrivacyViolation, 'depth|nested archive'):
            privacy.validate_site(self.root)

    def test_v7_tar_header_is_detected_directly_and_when_nested(self):
        payload = b'synthetic private source fingerprint fixture\n'
        raw = bytearray(self.raw_tar([('renamed.dat', b'0', payload)]))
        raw[257:265] = b'\0' * 8
        raw[148:156] = b'        '
        checksum = sum(raw[:512])
        raw[148:156] = f'{checksum:06o}\0 '.encode('ascii')
        direct = self.root / 'downloads/opaque.dat'
        direct.parent.mkdir(parents=True)
        direct.write_bytes(raw)
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {hashlib.sha256(payload).hexdigest()}):
            with self.assertRaisesRegex(privacy.PrivacyViolation, 'fingerprint'):
                privacy.validate_site(self.root)

        direct.unlink()
        nested = self.raw_tar([('opaque.dat', b'0', bytes(raw))])
        nested_path = self.root / 'downloads/nested.dat'
        nested_path.write_bytes(nested)
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {hashlib.sha256(payload).hexdigest()}):
            with self.assertRaisesRegex(privacy.PrivacyViolation, 'fingerprint|nested archive'):
                privacy.validate_site(self.root)

    def test_compressed_css_and_javascript_resources_pass_but_source_fingerprint_fails(self):
        assets = self.root / 'downloads/assets'
        assets.mkdir(parents=True)
        (assets / 'theme.css.gz').write_bytes(gzip.compress(b'body { color: navy; }'))
        (assets / 'app.js.bz2').write_bytes(bz2.compress(b'const safe = true;'))
        privacy.validate_site(self.root)

        payload = b'synthetic private source fingerprint fixture\n'
        (assets / 'opaque.gz').write_bytes(gzip.compress(payload))
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {hashlib.sha256(payload).hexdigest()}):
            with self.assertRaisesRegex(privacy.PrivacyViolation, 'fingerprint'):
                privacy.validate_site(self.root)

    def test_tar_extension_metadata_and_padding_share_the_content_budget(self):
        large_pax = self.pax_record('comment', 'x' * 65_500)
        large_gnu_name = b'a' * 65_536 + b'\0'
        for label, entries in (
            ('pax', [('PaxHeaders/file', b'x', large_pax), ('file.txt', b'0', b'x')]),
            ('gnu', [('././@LongLink', b'L', large_gnu_name), ('file.txt', b'0', b'x')]),
        ):
            with self.subTest(label=label):
                path = self.root / 'firmware' / f'{label}.tar'
                path.write_bytes(self.raw_tar(entries))
                with mock.patch.object(privacy, 'MAX_ARCHIVE_MEMBER_BYTES', 16), \
                     mock.patch.object(privacy, 'MAX_ARCHIVE_CONTENT_BYTES', 80_000):
                    with self.assertRaisesRegex(privacy.PrivacyViolation, 'extended header'):
                        privacy.validate_site(self.root)

        small = self.root / 'firmware/padding.tar'
        small.write_bytes(self.raw_tar([('empty', b'0', b'')]))
        with mock.patch.object(privacy, 'MAX_ARCHIVE_CONTENT_BYTES', 512):
            with self.assertRaisesRegex(privacy.PrivacyViolation, 'content|limit'):
                privacy.validate_site(self.root)

    def test_tar_extended_headers_count_toward_member_budget_and_recursion_is_normalized(self):
        entries = [
            (f'PaxHeaders/{index}', b'x', self.pax_record('comment', str(index)))
            for index in range(3)
        ] + [('file.txt', b'0', b'x')]
        path = self.root / 'firmware/pax-count.tar'
        path.write_bytes(self.raw_tar(entries))
        with mock.patch.object(privacy, 'MAX_ARCHIVE_MEMBERS', 1):
            with self.assertRaisesRegex(privacy.PrivacyViolation, 'member|header|limit'):
                privacy.validate_site(self.root)

        raw = path.read_bytes()
        with mock.patch.object(privacy.tarfile, 'open', side_effect=RecursionError('synthetic recursion')):
            with self.assertRaisesRegex(privacy.PrivacyViolation, 'recursion|safely inspect'):
                privacy._inspect_tar(raw, 'pax-count.tar', 0, privacy._InspectionBudget())

    def test_zip_source_is_rejected_under_an_alternate_filename(self):
        archive = self.root / 'firmware/opaque-package.data'
        archive.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as output:
            for name, _, payload in self.loader_layout_entries():
                output.writestr(name, payload)
        with self.assertRaisesRegex(privacy.PrivacyViolation, 'loader source layout|fingerprint'):
            privacy.validate_site(self.root)

    def test_benign_zip_passes_and_directory_payload_is_rejected(self):
        archive = self.root / 'firmware/benign.zip'
        with zipfile.ZipFile(archive, 'w') as output:
            output.writestr('readme.txt', 'benign package metadata')
        privacy.validate_site(self.root)

        archive.unlink()
        with zipfile.ZipFile(archive, 'w') as output:
            info = zipfile.ZipInfo('loader/')
            info.create_system = 3
            info.external_attr = (stat.S_IFDIR | 0o755) << 16 | 0x10
            output.writestr(info, b'synthetic directory payload')
        with self.assertRaisesRegex(privacy.PrivacyViolation, 'directory'):
            privacy.validate_site(self.root)

    def test_prefixed_zip_is_inspected_directly_and_when_nested(self):
        payload = b'synthetic private loader fingerprint fixture; not real source code\n'
        fingerprint = hashlib.sha256(payload).hexdigest()

        def make_zip(contents):
            output = io.BytesIO()
            with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('application/opaque.bin', contents)
            return output.getvalue()

        benign_zip = make_zip(b'synthetic benign archive fixture\n')
        prefixed_benign_zip = b'MZ synthetic benign self-extractor prefix\n' + benign_zip
        prefixed_private_zip = b'MZ synthetic benign self-extractor prefix\n' + make_zip(payload)
        self.assertTrue(zipfile.is_zipfile(io.BytesIO(prefixed_private_zip)))

        archive = self.root / 'downloads/opaque.dat'
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(benign_zip)
        privacy.validate_site(self.root)
        archive.write_bytes(prefixed_benign_zip)
        privacy.validate_site(self.root)

        archive.write_bytes(self.raw_tar([
            ('application/opaque.dat', b'0', prefixed_benign_zip),
        ]))
        privacy.validate_site(self.root)

        archive.write_bytes(prefixed_private_zip)
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
            with self.assertRaisesRegex(
                    privacy.PrivacyViolation,
                    'Private loader source fingerprint found in archive'):
                privacy.validate_site(self.root)

        archive.write_bytes(self.raw_tar([
            ('application/opaque.dat', b'0', prefixed_private_zip),
        ]))
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
            with self.assertRaisesRegex(
                    privacy.PrivacyViolation,
                    'Private loader source fingerprint found in archive'):
                privacy.validate_site(self.root)

        archive.write_bytes(b'MZ synthetic benign self-extractor prefix\n' + make_zip(prefixed_private_zip))
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
            with self.assertRaisesRegex(
                    privacy.PrivacyViolation,
                    'Private loader source fingerprint found in archive'):
                privacy.validate_site(self.root)

    def test_gnu_sparse_tar_member_is_rejected_but_regular_tar_passes(self):
        archive = self.root / 'downloads/opaque.dat'
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(self.raw_tar([('application/opaque.dat', b'0', b'benign')]))
        privacy.validate_site(self.root)

        info = tarfile.TarInfo('application/opaque.dat')
        info.type = tarfile.GNUTYPE_SPARSE
        info.size = 1
        header = bytearray(info.tobuf(format=tarfile.GNU_FORMAT))
        header[386:398] = b'00000000000\0'
        header[398:410] = b'00000000001\0'
        header[483:495] = f'{131072:011o}\0'.encode('ascii')
        header[148:156] = b'        '
        checksum = sum(header)
        header[148:156] = f'{checksum:06o}\0 '.encode('ascii')
        sparse_tar = bytes(header) + b'X' + b'\0' * 511 + b'\0' * 1024
        self.assertEqual(len(sparse_tar), 2048)
        with tarfile.open(fileobj=io.BytesIO(sparse_tar), mode='r:') as archive_file:
            member = archive_file.next()
            self.assertTrue(member.issparse())
            self.assertEqual(member.size, 131072)

        archive.write_bytes(sparse_tar)
        with mock.patch.object(privacy, 'MAX_ARCHIVE_CONTENT_BYTES', 2048):
            with self.assertRaisesRegex(privacy.PrivacyViolation, 'TAR sparse members are not supported'):
                privacy.validate_site(self.root)

    def test_raw_loader_source_path_is_rejected(self):
        path = self.root / 'firmware/vendor/loader/implementation.cpp'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('int private_loader_source;\n')
        with self.assertRaises(privacy.PrivacyViolation):
            privacy.validate_site(self.root)

    def test_raw_source_fingerprint_is_detected_after_renaming(self):
        payload = b'synthetic private source fingerprint fixture\n'
        path = self.root / 'firmware/renamed.dat'
        path.write_bytes(payload)
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {hashlib.sha256(payload).hexdigest()}):
            with self.assertRaises(privacy.PrivacyViolation):
                privacy.validate_site(self.root)

    def test_loader_provenance_cannot_publish_source_metadata(self):
        self.write_json('data/firmware-catalog.json', {
            'devices': [{'id': 't147-lora-dualboot', 'provenance': {
                'loader': {'version': 'Legacy-20261004', 'sourceState': 'local-uncommitted',
                           'sourceArtifact': 'private.dat', 'sourceSha256': '1' * 64},
            }}],
        })
        with self.assertRaises(privacy.PrivacyViolation):
            privacy.validate_site(self.root)

    def test_release_cannot_list_loader_as_a_source_artifact(self):
        self.write_json('firmware/t147-dualboot/release.json', {
            'sourceArtifacts': {'loader': {'file': 'firmware/opaque.dat'}},
        })
        with self.assertRaises(privacy.PrivacyViolation):
            privacy.validate_site(self.root)

    def test_loader_source_state_without_archive_metadata_is_allowed(self):
        self.write_json('data/firmware-catalog.json', {
            'devices': [{'id': 't147-lora-dualboot', 'provenance': {
                'loader': {'version': 'Legacy-20261004', 'commit': None, 'source': None,
                           'sourceState': 'local-uncommitted'},
                'wadamesh': {'sourceArtifact': 'firmware/wadamesh-source.tar.gz', 'sourceSha256': '2' * 64},
                'meshtastic': {'sourceArtifact': 'firmware/meshtastic-source.tar.gz', 'sourceSha256': '3' * 64},
            }}],
        })
        self.write_json('firmware/t147-dualboot/release.json', {
            'sourceArtifacts': {'wadamesh': {}, 'meshtastic': {}},
        })
        privacy.validate_site(self.root)

    def test_archive_path_traversal_and_escaping_symlink_are_rejected(self):
        cases = [
            [('../escape.cpp', 'file', b'private source')],
            [('tree/escape.cpp', 'symlink', b'../../outside.cpp')],
        ]
        for index, entries in enumerate(cases):
            with self.subTest(index=index):
                for path in (self.root / 'firmware').iterdir():
                    if path.is_file():
                        path.unlink()
                self.write_tar(self.root / 'firmware/unsafe.tar.gz', entries)
                with self.assertRaises(privacy.PrivacyViolation):
                    privacy.validate_site(self.root)

    def test_unsupported_archive_format_is_rejected_even_when_renamed(self):
        path = self.root / 'firmware/opaque.data'
        path.write_bytes(b'7z\xbc\xaf\x27\x1c' + b'opaque')
        with self.assertRaises(privacy.PrivacyViolation):
            privacy.validate_site(self.root)

    def test_archive_member_and_content_limits_are_enforced(self):
        archive = self.root / 'firmware/bounded.tar.gz'
        self.write_tar(archive, [
            ('one.txt', 'file', b'123'),
            ('two.txt', 'file', b'456'),
        ])
        with mock.patch.object(privacy, 'MAX_ARCHIVE_MEMBERS', 1):
            with self.assertRaises(privacy.PrivacyViolation):
                privacy.validate_site(self.root)
        with mock.patch.object(privacy, 'MAX_ARCHIVE_CONTENT_BYTES', 5):
            with self.assertRaises(privacy.PrivacyViolation):
                privacy.validate_site(self.root)

        zip_archive = self.root / 'firmware/bounded.zip'
        with zipfile.ZipFile(zip_archive, 'w') as output:
            output.writestr('one.txt', b'1')
            output.writestr('two.txt', b'2')
        with mock.patch.object(privacy, 'MAX_ARCHIVE_MEMBERS', 1):
            with self.assertRaises(privacy.PrivacyViolation):
                privacy.validate_site(self.root)

    def test_site_symlink_is_rejected_without_following_it(self):
        outside = Path(self.temp.name) / 'outside'
        outside.write_text('not part of the site')
        (self.root / 'firmware/escape').symlink_to(outside)
        with self.assertRaises(privacy.PrivacyViolation):
            privacy.validate_site(self.root)

    def test_walk_permission_errors_and_file_stat_errors_fail_closed(self):
        def denied_walk(root, **kwargs):
            onerror = kwargs.get('onerror')
            if onerror:
                onerror(PermissionError('synthetic unreadable directory'))
            return iter(())

        with mock.patch.object(privacy.os, 'walk', side_effect=denied_walk):
            with self.assertRaisesRegex(privacy.PrivacyViolation, 'traverse|walk|directory'):
                privacy.validate_site(self.root)

        file_path = self.root / 'firmware/unreadable.txt'
        file_path.write_text('ordinary text')
        original_lstat = Path.lstat

        def failing_lstat(path):
            if path == file_path:
                raise PermissionError('synthetic stat denial')
            return original_lstat(path)

        with mock.patch.object(Path, 'lstat', failing_lstat):
            with self.assertRaisesRegex(privacy.PrivacyViolation, 'inspect public file|stat'):
                privacy.validate_site(self.root)

        original_open = Path.open

        def failing_open(path, *args, **kwargs):
            if path == file_path:
                raise PermissionError('synthetic read denial')
            return original_open(path, *args, **kwargs)

        with mock.patch.object(Path, 'open', failing_open):
            with self.assertRaisesRegex(privacy.PrivacyViolation, 'Cannot read public file'):
                privacy.validate_site(self.root)

    def test_deep_json_is_reported_as_privacy_violation(self):
        path = self.root / 'data/deep.json'
        path.parent.mkdir(parents=True)
        path.write_text('[' * 1200 + '0' + ']' * 1200)
        with self.assertRaisesRegex(privacy.PrivacyViolation, 'depth|JSON|safely inspect'):
            privacy.validate_site(self.root)

    def write_binary(self, relative, data):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    @staticmethod
    def marker_payload():
        return b'synthetic private source fingerprint fixture for prefix containers\n'

    @staticmethod
    def zip_bytes(entries):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, data in entries.items():
                archive.writestr(name, data)
        return buffer.getvalue()

    def test_prefixed_containers_cannot_hide_loader_source(self):
        payload = self.marker_payload()
        fingerprint = hashlib.sha256(payload).hexdigest()
        junk = b'MZ synthetic self-extractor prefix fixture\n'
        layout = [(name, b'0', data) for name, _kind, data in self.loader_layout_entries()]
        fixtures = {
            'downloads/prefixed-tar.dat': junk + self.raw_tar(layout),
            'downloads/prefixed-gzip.dat': junk + gzip.compress(payload),
            'downloads/prefixed-bzip2.dat': junk + bz2.compress(payload),
            'downloads/prefixed-xz.dat': junk + lzma.compress(payload),
            'downloads/prefixed-7z.dat': junk + b'7z\xbc\xaf\x27\x1c' + bytes(32),
            'downloads/prefixed-zstd.dat': junk + b'\x28\xb5\x2f\xfd\x00' + bytes(32),
        }
        for relative, data in fixtures.items():
            with self.subTest(relative=relative):
                path = self.write_binary(relative, data)
                with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
                    with self.assertRaises(privacy.PrivacyViolation):
                        privacy.validate_site(self.root)
                path.unlink()

    def test_prefixed_containers_inside_archive_members_are_inspected(self):
        payload = self.marker_payload()
        fingerprint = hashlib.sha256(payload).hexdigest()
        junk = b'MZ synthetic self-extractor prefix fixture\n'
        member = junk + gzip.compress(payload)
        self.write_binary('firmware/outer.zip', self.zip_bytes({'bundles/inner.dat': member}))
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
            with self.assertRaises(privacy.PrivacyViolation):
                privacy.validate_site(self.root)
        shutil.rmtree(self.root / 'firmware')
        (self.root / 'firmware').mkdir()
        self.write_binary('firmware/outer.tar', self.raw_tar([('bundles/inner.dat', b'0', member)]))
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
            with self.assertRaises(privacy.PrivacyViolation):
                privacy.validate_site(self.root)

    def test_concatenated_zip_prefix_is_inspected(self):
        payload = self.marker_payload()
        private_zip = self.zip_bytes({'priv.dat': payload})
        benign_zip = self.zip_bytes({'readme.txt': b'benign\n'})
        fingerprint = hashlib.sha256(payload).hexdigest()
        for name, data in (('private-first', private_zip + benign_zip),
                           ('private-last', benign_zip + private_zip)):
            with self.subTest(name=name):
                path = self.write_binary(f'downloads/{name}.dat', data)
                with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
                    with self.assertRaises(privacy.PrivacyViolation):
                        privacy.validate_site(self.root)
                path.unlink()

    def test_self_extracting_zip_prefix_without_private_data_passes(self):
        self.write_binary('downloads/installer.dat',
                          b'MZ synthetic self-extractor prefix fixture\n' + self.zip_bytes({'readme.txt': b'benign\n'}))
        privacy.validate_site(self.root)

    def test_loader_metadata_variants_are_rejected(self):
        variants = (
            {'provenance': {'loader': {'source_artifact': 'loader-source-abc.tar.gz'}}},
            {'sourceArtifacts': ['loader-source-abc.tar.gz', 'meshtastic-source-x.tar.gz']},
            {'sourceArtifacts': [{'loader': {}}]},
        )
        for index, value in enumerate(variants):
            with self.subTest(index=index):
                path = self.write_json(f'data/metadata-{index}.json', value)
                with self.assertRaises(privacy.PrivacyViolation):
                    privacy.validate_site(self.root)
                path.unlink()

    def test_bootloader_metadata_key_is_not_a_false_positive(self):
        self.write_json('data/metadata.json', {'sourceArtifacts': {'bootloader': {'file': 'bootloader.bin'}}})
        privacy.validate_site(self.root)

    def test_corrupt_compressed_resource_fails_cleanly(self):
        broken = b'\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\x03\xff\xff'
        path = self.write_binary('downloads/assets/broken.css.gz', broken)
        with self.assertRaisesRegex(privacy.PrivacyViolation, 'Cannot safely decompress'):
            privacy.validate_site(self.root)
        path.unlink()
        self.write_binary('firmware/bundle.tar', self.raw_tar([('assets/broken.css.gz', b'0', broken)]))
        with self.assertRaisesRegex(privacy.PrivacyViolation, 'Cannot safely decompress'):
            privacy.validate_site(self.root)

    def test_empty_member_flood_is_rejected_quickly(self):
        flood = gzip.compress(b'') * 20_000
        self.write_binary('downloads/assets/flood.css.gz', flood)
        started = time.monotonic()
        with self.assertRaisesRegex(privacy.PrivacyViolation, 'concatenated members'):
            privacy.validate_site(self.root)
        self.assertLess(time.monotonic() - started, 30)

    def test_directory_named_like_private_archive_is_rejected(self):
        directory = self.root / 'firmware/loader-source-3ee5e90e33f21b11'
        directory.mkdir(parents=True)
        (directory / 'readme.txt').write_text('benign\n')
        with self.assertRaisesRegex(privacy.PrivacyViolation, 'Private loader source archive name'):
            privacy.validate_site(self.root)

    def test_benign_embedded_streams_do_not_false_positive(self):
        ramp = bytes(range(256)) * 40
        self.write_binary('firmware/firmware.bin',
                          ramp + b'\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\x03' + ramp)
        self.write_binary('firmware/packed.bin',
                          b'\x00' * 16 + gzip.compress(b'compressed section payload\n') + b'\x00' * 16)
        self.write_binary('downloads/installer.dat',
                          b'MZ synthetic self-extractor prefix fixture\n' + self.zip_bytes({'readme.txt': b'benign\n'}))
        privacy.validate_site(self.root)

    @staticmethod
    def gzip_with_fields(payload, fname=None, fcomment=None, fextra=None):
        compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
        deflated = compressor.compress(payload) + compressor.flush()
        flags = 0
        fields = b''
        if fextra:
            flags |= 0x04
            fields += len(fextra).to_bytes(2, 'little') + fextra
        if fname:
            flags |= 0x08
            fields += fname + b'\x00'
        if fcomment:
            flags |= 0x10
            fields += fcomment + b'\x00'
        header = bytes([0x1f, 0x8b, 8, flags]) + b'\x00' * 4 + b'\x00\x03' + fields
        return header + deflated + struct.pack('<II', zlib.crc32(payload) & 0xffffffff,
                                               len(payload) & 0xffffffff)

    @staticmethod
    def zip_with_region(entries, comment=b'', extra=None):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, data in entries.items():
                if extra is None:
                    archive.writestr(name, data)
                else:
                    info = zipfile.ZipInfo(name)
                    info.extra = extra
                    archive.writestr(info, data)
            if comment:
                archive.comment = comment
        return buffer.getvalue()

    @staticmethod
    def zip_with_gap(gap):
        archive = bytearray(SourcePrivacyTests.zip_with_region({'readme.txt': b'benign\n'}))
        end = archive.rfind(b'PK\x05\x06')
        directory_offset = struct.unpack_from('<I', archive, end + 16)[0]
        archive[directory_offset:directory_offset] = gap
        struct.pack_into('<I', archive, end + len(gap) + 16, directory_offset + len(gap))
        return bytes(archive)

    def test_partial_compressed_streams_cannot_hide_private_content(self):
        payload = self.marker_payload()
        fingerprint = hashlib.sha256(payload).hexdigest()
        tail = b'EXTRAGARBAGE-NONZERO'
        fixtures = {
            'downloads/partial-gzip.dat': b'X' + gzip.compress(payload) + tail,
            'downloads/partial-bzip2.dat': b'X' + bz2.compress(payload) + tail,
            'downloads/partial-xz.dat': b'X' + lzma.compress(payload) + tail,
            'downloads/partial-tar-member.dat': self.raw_tar(
                [('x.dat', b'0', b'X' + gzip.compress(payload) + tail)]),
            'downloads/partial-zip-member.dat': self.zip_bytes(
                {'x.dat': b'X' + gzip.compress(payload) + tail}),
        }
        for relative, data in fixtures.items():
            with self.subTest(relative=relative):
                path = self.write_binary(relative, data)
                with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
                    with self.assertRaises(privacy.PrivacyViolation):
                        privacy.validate_site(self.root)
                path.unlink()

    def test_zip_uninspected_regions_are_audited(self):
        payload = self.marker_payload()
        fingerprint = hashlib.sha256(payload).hexdigest()
        benign_extra = b'UT' + struct.pack('<H', 5) + b'\x01' + struct.pack('<I', 0)
        fixtures = {
            'downloads/zip-gap.dat': self.zip_with_gap(payload),
            'downloads/zip-comment.dat': self.zip_with_region({'readme.txt': b'benign\n'}, comment=payload),
            'downloads/zip-extra.dat': self.zip_with_region({'readme.txt': b'benign\n'}, extra=payload),
        }
        for relative, data in fixtures.items():
            with self.subTest(relative=relative):
                path = self.write_binary(relative, data)
                with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
                    with self.assertRaises(privacy.PrivacyViolation):
                        privacy.validate_site(self.root)
                path.unlink()
        self.write_binary('downloads/zip-benign-regions.dat',
                          self.zip_with_region({'readme.txt': b'benign\n'}, comment=b'build fixture',
                                               extra=benign_extra))
        privacy.validate_site(self.root)

    def test_tar_side_channels_are_audited(self):
        padding_tar = bytearray(self.raw_tar([('note.txt', b'0', b'short payload')]))
        start = 512 + len(b'short payload')
        padding_tar[start:start + 8] = b'LEAKED!!'
        fixtures = {
            'downloads/tar-padding.tar': bytes(padding_tar),
            'downloads/tar-pax.tar': self.raw_tar([('PaxHeaders/x', b'x', b'leaked pax body\n'),
                                                   ('x', b'0', b'benign\n')]),
            'downloads/tar-longlink.tar': self.raw_tar([('././@LongLink', b'L', b'leaked long name\n\x00'),
                                                        ('x', b'0', b'benign\n')]),
        }
        for relative, data in fixtures.items():
            with self.subTest(relative=relative):
                path = self.write_binary(relative, data)
                if relative.endswith('tar-pax.tar'):
                    with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS',
                                           {hashlib.sha256(b'leaked pax body\n').hexdigest()}):
                        with self.assertRaises(privacy.PrivacyViolation):
                            privacy.validate_site(self.root)
                else:
                    with self.assertRaises(privacy.PrivacyViolation):
                        privacy.validate_site(self.root)
                path.unlink()
        self.write_binary('downloads/tar-benign.tar', self.raw_tar([('x', b'0', b'benign\n')]))
        privacy.validate_site(self.root)

    def test_gzip_header_fields_are_audited(self):
        payload = self.marker_payload()
        fingerprint = hashlib.sha256(payload).hexdigest()
        fixtures = {
            'downloads/assets/comment.css.gz': self.gzip_with_fields(b'body{color:red}', fcomment=payload),
            'downloads/assets/extra.css.gz': self.gzip_with_fields(b'body{color:red}', fextra=payload),
            'downloads/assets/name.css.gz': self.gzip_with_fields(b'body{color:red}',
                                                                  fname=b'loader-source-abc.tar.gz'),
        }
        for relative, data in fixtures.items():
            with self.subTest(relative=relative):
                path = self.write_binary(relative, data)
                with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
                    with self.assertRaises(privacy.PrivacyViolation):
                        privacy.validate_site(self.root)
                path.unlink()
        self.write_binary('downloads/assets/benign.css.gz',
                          self.gzip_with_fields(b'body{color:red}', fcomment=b'build 1234'))
        privacy.validate_site(self.root)

    def test_unlisted_container_formats_are_rejected(self):
        payload = self.marker_payload()
        fingerprint = hashlib.sha256(payload).hexdigest()
        skippable = b'\x50\x2a\x4d\x18' + struct.pack('<I', len(payload)) + payload
        fixtures = {
            'downloads/skippable.dat': skippable,
            'downloads/lzma-alone.dat': lzma.compress(payload, format=lzma.FORMAT_ALONE),
            'downloads/lzma-alone.lzma': lzma.compress(payload, format=lzma.FORMAT_ALONE),
        }
        for relative, data in fixtures.items():
            with self.subTest(relative=relative):
                path = self.write_binary(relative, data)
                with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
                    with self.assertRaises(privacy.PrivacyViolation):
                        privacy.validate_site(self.root)
                path.unlink()

    def test_metadata_homoglyphs_and_underscores_are_rejected(self):
        variants = (
            {'provenance': {'load\u00e9r': {'sourceArtifact': 'x'}}},
            {'provenance': {'\uff4c\uff4f\uff41\uff44\uff45\uff52': {'sourceArtifact': 'x'}}},
            {'note': 'loader_source-abc.tar.gz'},
        )
        for index, value in enumerate(variants):
            with self.subTest(index=index):
                path = self.write_json(f'data/homoglyph-{index}.json', value)
                with self.assertRaises(privacy.PrivacyViolation):
                    privacy.validate_site(self.root)
                path.unlink()

    def test_truncated_zip_local_records_are_audited(self):
        payload = self.marker_payload()
        fingerprint = hashlib.sha256(payload).hexdigest()
        truncated = b'X' + self.zip_bytes({'priv.dat': payload})[:-22]
        path = self.write_binary('downloads/truncated.dat', truncated)
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
            with self.assertRaises(privacy.PrivacyViolation):
                privacy.validate_site(self.root)
        path.unlink()
        self.write_binary('downloads/truncated-benign.dat',
                          b'X' + self.zip_bytes({'readme.txt': b'benign\n'})[:-22])
        privacy.validate_site(self.root)

    # ------------------------------------------------------------------
    # Round 4 adversarial closures (R3-01 .. R3-11)
    # ------------------------------------------------------------------

    @staticmethod
    def crafted_dir_zip(payload, with_dir_attr=True, name=b'd/'):
        """Local+central directory entry declaring compress_size but no payload use."""
        ext = ((stat.S_IFDIR | 0o755) << 16) if with_dir_attr else 0
        local = (b'PK\x03\x04' + struct.pack('<HHHHHIIIHH', 20, 0, 0, 0, 0x21, 0,
                                             len(payload), 0, len(name), 0) + name + payload)
        central = (b'PK\x01\x02' + struct.pack('<HHHHHHIIIHHHHHII', 20, 20, 0, 0, 0, 0x21, 0,
                                               len(payload), 0, len(name), 0, 0, 0, 0, ext, 0)
                   + name)
        end = b'PK\x05\x06' + struct.pack('<HHHHIIH', 0, 0, 1, 1, len(central), len(local), 0)
        return local + central + end

    @staticmethod
    def crafted_descriptor_zip(payload, prefix=b'X', name=b'p.dat'):
        """Local record with the data-descriptor flag and zero declared sizes, no EOCD."""
        local = (b'PK\x03\x04' + struct.pack('<HHHHHIIIHH', 20, 0x08, 0, 0, 0x21, 0, 0, 0,
                                             len(name), 0) + name + payload)
        descriptor = b'PK\x07\x08' + struct.pack(
            '<III', zlib.crc32(payload) & 0xffffffff, len(payload), len(payload))
        return prefix + local + descriptor

    @staticmethod
    def raw_tar_with_prefix(prefix, name=b'x.txt'):
        header = bytearray(512)
        header[:len(name)] = name
        header[100:108] = b'0000644\0'
        header[108:116] = b'0000000\0'
        header[116:124] = b'0000000\0'
        header[124:136] = b'00000000000\0'
        header[136:148] = b'00000000000\0'
        header[148:156] = b'        '
        header[156:157] = b'0'
        header[257:263] = b'ustar\0'
        header[263:265] = b'00'
        header[345:345 + len(prefix)] = prefix[:155]
        checksum = sum(header)
        header[148:156] = f'{checksum:06o}\0 '.encode('ascii')
        return bytes(header) + b'\0' * 1024

    def test_pax_size_spoof_cannot_hide_raw_member_payload(self):
        payload = self.marker_payload()
        fingerprint = hashlib.sha256(payload).hexdigest()
        spoofed = self.raw_tar([('PaxHeaders/f.txt', b'x', self.pax_record('size', '0')),
                                ('f.txt', b'0', payload)])
        self.write_binary('firmware/spoof.tar', spoofed)
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
            with self.assertRaises(privacy.PrivacyViolation):
                privacy.validate_site(self.root)
        (self.root / 'firmware/spoof.tar').unlink()
        plain = self.raw_tar([('f.txt', b'0', b'benign payload\n')])
        self.write_binary('firmware/plain.tar', plain)
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
            privacy.validate_site(self.root)

    def test_zip_entry_comment_and_entry_name_are_audited(self):
        payload = self.marker_payload()
        fingerprint = hashlib.sha256(payload).hexdigest()
        archive = self.root / 'firmware/entry-comment.zip'
        with zipfile.ZipFile(archive, 'w') as output:
            info = zipfile.ZipInfo('readme.txt')
            info.comment = payload
            output.writestr(info, b'benign\n')
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
            with self.assertRaises(privacy.PrivacyViolation):
                privacy.validate_site(self.root)
        archive.unlink()
        with zipfile.ZipFile(archive, 'w') as output:
            info = zipfile.ZipInfo('readme.txt')
            info.comment = b'build fixture'
            output.writestr(info, b'benign\n')
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
            privacy.validate_site(self.root)
        archive.unlink()
        marker_name = ('PRIVNAME_' + 'N' * 90).encode('ascii')
        with zipfile.ZipFile(archive, 'w') as output:
            output.writestr(marker_name.decode('ascii'), b'benign\n')
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS',
                               {hashlib.sha256(marker_name).hexdigest()}):
            with self.assertRaises(privacy.PrivacyViolation):
                privacy.validate_site(self.root)

    def test_zip_directory_entry_cannot_declare_covered_bytes(self):
        payload = self.marker_payload()
        fingerprint = hashlib.sha256(payload).hexdigest()
        archive = self.root / 'firmware/dir-trick.dat'
        archive.write_bytes(self.crafted_dir_zip(payload))
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
            with self.assertRaises(privacy.PrivacyViolation):
                privacy.validate_site(self.root)
        archive.write_bytes(self.crafted_dir_zip(payload, with_dir_attr=False))
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
            with self.assertRaises(privacy.PrivacyViolation):
                privacy.validate_site(self.root)
        archive.write_bytes(self.crafted_dir_zip(b'\0' * len(payload)))
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
            privacy.validate_site(self.root)

    def test_gzip_later_member_side_fields_are_audited(self):
        payload = self.marker_payload()
        fingerprint = hashlib.sha256(payload).hexdigest()
        first = gzip.compress(b'a\n')
        fixtures = {
            'assets/member2-comment.css.gz':
                first + self.gzip_with_fields(b'b\n', fcomment=payload),
            'assets/member2-extra.css.gz':
                first + self.gzip_with_fields(b'b\n', fextra=payload),
            'assets/member2-name.css.gz':
                first + self.gzip_with_fields(b'b\n', fname=payload),
        }
        for relative, data in fixtures.items():
            with self.subTest(relative=relative):
                path = self.write_binary(relative, data)
                with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
                    with self.assertRaises(privacy.PrivacyViolation):
                        privacy.validate_site(self.root)
                path.unlink()
        benign = self.write_binary('assets/benign-member2.css.gz',
                                   first + self.gzip_with_fields(b'b\n', fcomment=b'build 1234'))
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
            privacy.validate_site(self.root)
        benign.unlink()

    def test_tar_pax_values_keys_and_global_headers_are_audited(self):
        payload = b'synthetic private pax value fixture ' + b'P' * 64
        fingerprint = hashlib.sha256(payload).hexdigest()
        value_pax = self.pax_record('comment', payload.decode('ascii'))
        key_bytes = b'PRIVKEY_' + b'K' * 120
        key_pax = self.pax_record(key_bytes.decode('ascii'), 'v')
        fixtures = {
            'firmware/pax-value.tar': self.raw_tar(
                [('PaxHeaders/x', b'x', value_pax), ('x', b'0', b'benign\n')]),
            'firmware/pax-global.tar': self.raw_tar(
                [('pax_global', b'g', value_pax), ('x', b'0', b'benign\n')]),
            'firmware/pax-key.tar': self.raw_tar(
                [('PaxHeaders/x', b'x', key_pax), ('x', b'0', b'benign\n')]),
        }
        for relative, data in fixtures.items():
            with self.subTest(relative=relative):
                path = self.write_binary(relative, data)
                expected = hashlib.sha256(key_bytes).hexdigest() if 'key' in relative else fingerprint
                with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {expected}):
                    with self.assertRaises(privacy.PrivacyViolation):
                        privacy.validate_site(self.root)
                path.unlink()

    def test_tar_longlink_names_raw_names_and_prefix_fields_are_audited(self):
        payload = self.marker_payload()
        fingerprint = hashlib.sha256(payload).hexdigest()
        name_bytes = b'PRIVNAMEF_' + b'N' * 90
        fixtures = {
            'firmware/longlink-l.tar': self.raw_tar(
                [('././@LongLink', b'L', payload + b'\0'), ('x', b'0', b'benign\n')]),
            'firmware/longlink-k.tar': self.raw_tar(
                [('././@LongLink', b'K', payload + b'\0'), ('x', b'2', b'')]),
            'firmware/raw-name.tar': self.raw_tar([(name_bytes.decode('ascii'), b'0', b'benign\n')]),
            'firmware/prefix-field.tar': self.raw_tar_with_prefix(name_bytes),
        }
        for relative, data in fixtures.items():
            with self.subTest(relative=relative):
                path = self.write_binary(relative, data)
                expected = (hashlib.sha256(name_bytes).hexdigest()
                            if relative.endswith(('raw-name.tar', 'prefix-field.tar')) else fingerprint)
                with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {expected}):
                    with self.assertRaises(privacy.PrivacyViolation):
                        privacy.validate_site(self.root)
                path.unlink()

    def test_truncated_zip_data_descriptor_payload_is_recovered(self):
        payload = self.marker_payload()
        fingerprint = hashlib.sha256(payload).hexdigest()
        archive = self.root / 'firmware/descriptor.dat'
        archive.write_bytes(self.crafted_descriptor_zip(payload))
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
            with self.assertRaises(privacy.PrivacyViolation):
                privacy.validate_site(self.root)
        archive.write_bytes(self.crafted_descriptor_zip(b'benign stored payload\n'))
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
            privacy.validate_site(self.root)

    def test_zip_and_tar_symlink_targets_are_audited(self):
        payload = self.marker_payload()
        fingerprint = hashlib.sha256(payload).hexdigest()
        archive = self.root / 'firmware/link.zip'
        with zipfile.ZipFile(archive, 'w') as output:
            info = zipfile.ZipInfo('link.txt')
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            output.writestr(info, payload)
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
            with self.assertRaises(privacy.PrivacyViolation):
                privacy.validate_site(self.root)
        archive.unlink()
        with zipfile.ZipFile(archive, 'w') as output:
            info = zipfile.ZipInfo('link.txt')
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            output.writestr(info, b'target.txt')
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
            privacy.validate_site(self.root)
        archive.unlink()
        link_name = b'PRIVLINK_' + b'L' * 91
        tar = self.write_binary(
            'firmware/link.tar',
            self.raw_tar([('s.txt', b'2', link_name), ('x', b'0', b'benign\n')]))
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS',
                               {hashlib.sha256(link_name).hexdigest()}):
            with self.assertRaises(privacy.PrivacyViolation):
                privacy.validate_site(self.root)
        tar.unlink()

    def test_padded_zip_regions_and_comments_are_audited(self):
        payload = self.marker_payload()
        fingerprint = hashlib.sha256(payload).hexdigest()
        fixtures = {
            'downloads/gap-pad-first.dat': self.zip_with_gap(b'\0' * 8 + payload),
            'downloads/gap-pad-last.dat': self.zip_with_gap(payload + b'\0'),
            'downloads/comment-padded.dat': self.zip_with_region(
                {'readme.txt': b'benign\n'}, comment=b'\0' * 30_000 + payload + b'\0' * 1_000),
        }
        for relative, data in fixtures.items():
            with self.subTest(relative=relative):
                path = self.write_binary(relative, data)
                with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
                    with self.assertRaises(privacy.PrivacyViolation):
                        privacy.validate_site(self.root)
                path.unlink()

    def test_well_formed_extra_payload_is_audited(self):
        payload = self.marker_payload()
        fingerprint = hashlib.sha256(payload).hexdigest()
        framed = b'UT' + struct.pack('<H', len(payload)) + payload
        archive = self.root / 'firmware/extra-record.dat'
        archive.write_bytes(self.zip_with_region({'readme.txt': b'benign\n'}, extra=framed))
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
            with self.assertRaises(privacy.PrivacyViolation):
                privacy.validate_site(self.root)
        benign_extra = b'UT' + struct.pack('<H', 5) + b'\x01' + struct.pack('<I', 0)
        archive.write_bytes(self.zip_with_region({'readme.txt': b'benign\n'}, extra=benign_extra))
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
            privacy.validate_site(self.root)

    def test_embedded_container_at_region_start_is_detected(self):
        payload = self.marker_payload()
        fingerprint = hashlib.sha256(payload).hexdigest()
        inner = self.zip_bytes({'priv.dat': payload})
        fixtures = {
            'downloads/gap-zip-offset0.dat': self.zip_with_gap(inner),
            'downloads/gap-gzip-offset0.dat': self.zip_with_gap(gzip.compress(payload)),
            'downloads/gap-zstd-offset0.dat': self.zip_with_gap(b'\x28\xb5\x2f\xfd\x00' + bytes(32)),
            'downloads/gap-lzma-offset5.dat': self.zip_with_gap(
                b'AAAAA' + lzma.compress(payload, format=lzma.FORMAT_ALONE)),
        }
        for relative, data in fixtures.items():
            with self.subTest(relative=relative):
                path = self.write_binary(relative, data)
                with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
                    with self.assertRaises(privacy.PrivacyViolation):
                        privacy.validate_site(self.root)
                path.unlink()
        benign = self.write_binary('downloads/gap-benign-padding.dat', self.zip_with_gap(b'\0' * 64))
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
            privacy.validate_site(self.root)
        benign.unlink()

    def test_digit_homoglyph_metadata_keys_are_rejected(self):
        variants = (
            {'provenance': {'1oader': {'sourceArtifact': 'x.bin', 'sourceSha256': '0' * 64}}},
            {'provenance': {'l0ader': {'sourceArtifact': 'x.bin'}}},
            {'s0urceartifacts': {'loader': {'file': 'x.bin'}}},
        )
        for index, value in enumerate(variants):
            with self.subTest(index=index):
                path = self.write_json(f'data/digit-{index}.json', value)
                with self.assertRaises(privacy.PrivacyViolation):
                    privacy.validate_site(self.root)
                path.unlink()
        self.write_json('data/bootloader.json',
                        {'sourceArtifacts': {'bootloader': {'file': 'bootloader.bin'}}})
        privacy.validate_site(self.root)

    def test_plain_files_and_json_reference_values_are_scanned(self):
        fixtures = {
            'docs/readme-src.txt': b'see loader/src/implementation.cpp\n',
            'docs/readme-space.txt': b'ref: loader source-abc.tar.gz\n',
            'docs/readme-dash.txt': 'ref: loader\u2014source-abc.tar.gz\n'.encode('utf-8'),
            'data/ref.json': json.dumps({'note': 'see loader/src/implementation.cpp'}).encode('utf-8'),
        }
        for relative, data in fixtures.items():
            with self.subTest(relative=relative):
                path = self.write_binary(relative, data)
                with self.assertRaises(privacy.PrivacyViolation):
                    privacy.validate_site(self.root)
                path.unlink()
        self.write_binary('docs/benign.txt',
                          b'bootloader procedure; loaders only update images\n')
        privacy.validate_site(self.root)

    # ------------------------------------------------------------------
    # Round 5 adversarial closures (SC4-A/B/C/D/LZMA/REF/WIN)
    # ------------------------------------------------------------------

    @staticmethod
    def truncated_local(name_bytes=b'p.dat', payload=b'', extra=b'', flag=0, csize=None, fsize=0):
        csize = len(payload) if csize is None else csize
        header = (b'PK\x03\x04' + struct.pack('<HHHHHIIIHH', 20, flag, 0, 0, 0x21, 0,
                                             csize, fsize, len(name_bytes), len(extra)))
        return b'X' + header + name_bytes + extra + payload

    @staticmethod
    def stored_oversize_zip(visible=b'', hidden=b'', member=b'p.dat', crc=None):
        core = visible
        crc = zlib.crc32(core) if crc is None else crc
        payload = visible + hidden
        local = (b'PK\x03\x04' + struct.pack('<HHHHHIIIHH', 20, 0, 0, 0, 0x21, crc,
                                             len(payload), len(core), len(member), 0)
                 + member + payload)
        central = (b'PK\x01\x02' + struct.pack('<HHHHHHIIIHHHHHII', 20, 20, 0, 0, 0, 0x21, crc,
                                               len(payload), len(core), len(member), 0, 0, 0, 0, 0, 0)
                   + member)
        end = b'PK\x05\x06' + struct.pack('<HHHHIIH', 0, 0, 1, 1, len(central), len(local), 0)
        return local + central + end

    @staticmethod
    def deflate_oversize_zip(visible, hidden, member=b'p.dat'):
        compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
        compressed = compressor.compress(visible + hidden) + compressor.flush()
        crc = zlib.crc32(visible) & 0xffffffff
        local = (b'PK\x03\x04' + struct.pack('<HHHHHIIIHH', 20, 0, 8, 0, 0x21, crc,
                                             len(compressed), len(visible), len(member), 0)
                 + member + compressed)
        central = (b'PK\x01\x02' + struct.pack('<HHHHHHIIIHHHHHII', 20, 20, 0, 8, 0, 0x21, crc,
                                               len(compressed), len(visible), len(member),
                                               0, 0, 0, 0, 0, 0) + member)
        end = b'PK\x05\x06' + struct.pack('<HHHHIIH', 0, 0, 1, 1, len(central), len(local), 0)
        return local + central + end

    def test_truncated_zip_local_header_fields_are_audited(self):
        marker = self.marker_payload()
        fingerprint = hashlib.sha256(marker).hexdigest()
        extra = b'UT' + struct.pack('<H', len(marker)) + marker
        fixtures = {
            'downloads/trunc-name.dat': self.truncated_local(name_bytes=marker),
            'downloads/trunc-extra.dat': self.truncated_local(name_bytes=b'p.dat', extra=extra),
            'downloads/trunc-name-in-tar.tar': self.raw_tar(
                [('x.dat', b'0', self.truncated_local(name_bytes=marker))]),
        }
        for relative, data in fixtures.items():
            with self.subTest(relative=relative):
                path = self.write_binary(relative, data)
                with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
                    with self.assertRaises(privacy.PrivacyViolation):
                        privacy.validate_site(self.root)
                path.unlink()
        self.write_binary('downloads/trunc-benign.dat',
                          self.truncated_local(name_bytes=b'p.dat', payload=b'benign\n',
                                               csize=len(b'benign\n'), fsize=len(b'benign\n')))
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
            privacy.validate_site(self.root)

    def test_stored_oversize_zip_member_is_rejected(self):
        marker = self.marker_payload()
        fingerprint = hashlib.sha256(marker).hexdigest()
        fixtures = {
            'firmware/stored-oversize.zip': self.stored_oversize_zip(b'hello\n', marker),
            'firmware/stored-empty-oversize.zip': self.stored_oversize_zip(b'', marker),
            'firmware/deflate-oversize.zip': self.deflate_oversize_zip(b'hello\n', marker),
        }
        for relative, data in fixtures.items():
            with self.subTest(relative=relative):
                path = self.write_binary(relative, data)
                with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
                    with self.assertRaises(privacy.PrivacyViolation):
                        privacy.validate_site(self.root)
                path.unlink()
        self.write_binary('firmware/stored-exact.zip', self.stored_oversize_zip(b'benign\n', b''))
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
            privacy.validate_site(self.root)

    def test_compressed_tail_after_embedded_member_is_audited(self):
        marker = self.marker_payload()
        fingerprint = hashlib.sha256(marker).hexdigest()
        fixtures = {
            'downloads/gzip-tail.dat': b'X' * 40 + gzip.compress(b'benign stream\n') + marker,
            'downloads/bzip2-tail.dat': b'X' * 40 + bz2.compress(b'benign stream\n') + marker,
            'downloads/xz-tail.dat': b'X' * 40 + lzma.compress(b'benign stream\n') + marker,
            'downloads/gzip-tail.tar': self.raw_tar(
                [('x.dat', b'0', b'X' * 40 + gzip.compress(b'benign stream\n') + marker)]),
        }
        for relative, data in fixtures.items():
            with self.subTest(relative=relative):
                path = self.write_binary(relative, data)
                with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
                    with self.assertRaises(privacy.PrivacyViolation):
                        privacy.validate_site(self.root)
                path.unlink()
        self.write_binary('downloads/gzip-zero-tail.dat',
                          b'X' * 40 + gzip.compress(b'benign stream\n') + b'\0' * 64)
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
            privacy.validate_site(self.root)

    def test_large_padded_regions_are_audited(self):
        marker = self.marker_payload()
        fingerprint = hashlib.sha256(marker).hexdigest()
        for label, gap in (
                ('ff-first', marker + b'\xff' * (65537 - len(marker))),
                ('ff-last', b'\xff' * 20000 + marker),
                ('nul-middle', b'\0' * 40000 + marker + b'\0' * 30000),
        ):
            with self.subTest(label=label):
                path = self.write_binary(f'downloads/region-{label}.dat', self.zip_with_gap(gap))
                with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
                    with self.assertRaises(privacy.PrivacyViolation):
                        privacy.validate_site(self.root)
                path.unlink()
        self.write_binary('downloads/region-benign.dat', self.zip_with_gap(b'\xff' * 65537))
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
            privacy.validate_site(self.root)

    def test_lzma_alone_extended_dictionary_sizes_are_detected(self):
        marker = self.marker_payload()
        fingerprint = hashlib.sha256(marker).hexdigest()
        for dictionary in (1 << 13, 1 << 15, 1 << 17, 1 << 19):
            with self.subTest(dictionary=dictionary):
                stream = lzma.compress(marker, format=lzma.FORMAT_ALONE,
                                       filters=[{'id': lzma.FILTER_LZMA1, 'dict_size': dictionary}])
                path = self.write_binary(f'downloads/lzma-{dictionary}.dat', self.zip_with_gap(stream))
                with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
                    with self.assertRaises(privacy.PrivacyViolation):
                        privacy.validate_site(self.root)
                path.unlink()

    def test_leet_and_hyphenated_loader_keys_are_rejected(self):
        variants = (
            {'provenance': {'1oad3r': {'sourceArtifact': 'x.bin', 'sourceSha256': '0' * 64}}},
            {'provenance': {'lo-ader': {'sourceArtifact': 'x.bin'}}},
            {'provenance': {'l0ad3r': {'sourceArtifact': 'x.bin'}}},
            {'s0urc3artifact5': {'l04d3r': {'file': 'x.bin'}}},
        )
        for index, value in enumerate(variants):
            with self.subTest(index=index):
                path = self.write_json(f'data/leet-{index}.json', value)
                with self.assertRaises(privacy.PrivacyViolation):
                    privacy.validate_site(self.root)
                path.unlink()
        self.write_json('data/leet-ref.json', {'note': 'ref: lo-ader source-abc.tar.gz'})
        with self.assertRaises(privacy.PrivacyViolation):
            privacy.validate_site(self.root)
        (self.root / 'data/leet-ref.json').unlink()
        self.write_json('data/bootloader-leet.json',
                        {'sourceArtifacts': {'bootloader': {'file': 'bootloader.bin'}}})
        privacy.validate_site(self.root)

    def test_utf16_and_late_references_are_detected(self):
        self.write_binary('docs/utf16-ref.txt',
                          'see loader/src/implementation.cpp\n'.encode('utf-16-le'))
        with self.assertRaises(privacy.PrivacyViolation):
            privacy.validate_site(self.root)
        (self.root / 'docs/utf16-ref.txt').unlink()
        self.write_binary('docs/utf16-benign.txt',
                          'bootloader procedure documentation\n'.encode('utf-16-le'))
        privacy.validate_site(self.root)
        (self.root / 'docs/utf16-benign.txt').unlink()

    def test_zip_reference_beyond_scan_window_is_detected(self):
        big = b'x' * (16 * 1024 * 1024 + 4096)
        archive = self.root / 'firmware/late-ref.zip'
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_STORED) as output:
            output.writestr('big.bin', big)
            output.writestr('readme.txt', b'see loader/src/implementation.cpp\n')
        with self.assertRaises(privacy.PrivacyViolation):
            privacy.validate_site(self.root)
        archive.unlink()
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_STORED) as output:
            output.writestr('big.bin', big)
            output.writestr('readme.txt', b'benign package metadata\n')
        privacy.validate_site(self.root)

    # ------------------------------------------------------------------
    # Round 5.1 addendum: padded markers at every probe_runs=False site
    # ------------------------------------------------------------------

    def test_padded_markers_at_non_run_probe_sites_are_rejected(self):
        marker = self.marker_payload()
        fingerprint = hashlib.sha256(marker).hexdigest()
        half = len(marker) // 2
        gz = gzip.compress(b'benign-data')
        fixtures = {
            # embedded compressed tail (SC4-B site)
            'downloads/tail-ff.dat': b'\x00' * 40 + gz + marker + b'\xff' * 16,
            'downloads/tail-mixed.dat': b'\x00' * 40 + gz + marker + b'\x00' * 8 + b'\xff' * 8,
            'downloads/tail-leading.dat': b'\x00' * 40 + gz + b'\xff' * 8 + marker,
            'downloads/tail-interior.dat': b'\x00' * 40 + gz + marker[:half] + b'\xff' * 16 + marker[half:],
            # truncated ZIP fallback payload and unwalked remainder (SC4-A site)
            'downloads/zip-payload-pad.dat': self.truncated_local(
                name_bytes=b'ok.bin', payload=marker + b'\xff' * 8,
                csize=len(marker) + 8, fsize=len(marker) + 8),
            'downloads/zip-remainder-pad.dat': self.truncated_local(
                name_bytes=b'ok.bin', payload=b'benign', csize=6, fsize=6) + marker + b'\xff' * 8,
            # TAR body after a PAX header (SC4-A/R3-01 site)
            'downloads/tar-pax-body-pad.tar': self.raw_tar([
                ('PaxHeaders/x', b'x', self.pax_record('comment', 'benign')),
                ('x', b'0', marker + b'\xff' * 8)]),
        }
        for relative, data in fixtures.items():
            with self.subTest(relative=relative):
                path = self.write_binary(relative, data)
                with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
                    with self.assertRaises(privacy.PrivacyViolation):
                        privacy.validate_site(self.root)
                path.unlink()
        benign = {
            'downloads/tail-benign-pad.dat': b'\x00' * 40 + gz + b'benign tail' + b'\xff' * 16,
            'downloads/zip-payload-benign-pad.dat': self.truncated_local(
                name_bytes=b'ok.bin', payload=b'benign' + b'\xff' * 8,
                csize=14, fsize=14),
            'downloads/zip-remainder-benign-pad.dat': self.truncated_local(
                name_bytes=b'ok.bin', payload=b'benign', csize=6, fsize=6) + b'tail' + b'\xff' * 8,
            'downloads/tar-pax-benign-pad.tar': self.raw_tar([
                ('PaxHeaders/x', b'x', self.pax_record('comment', 'benign')),
                ('x', b'0', b'benign body' + b'\xff' * 8)]),
        }
        for relative, data in benign.items():
            with self.subTest(relative=relative):
                path = self.write_binary(relative, data)
                with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
                    privacy.validate_site(self.root)
                path.unlink()

    # ------------------------------------------------------------------
    # Round 6 adversarial closures (SC5-1 .. SC5-5)
    # ------------------------------------------------------------------

    @staticmethod
    def zip_bytes_stored(entries):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_STORED) as archive:
            for name, data in entries.items():
                archive.writestr(name, data)
        return buffer.getvalue()

    def test_padded_marker_copies_inside_members_and_expanded_payloads_are_rejected(self):
        marker = self.marker_payload()
        fingerprint = hashlib.sha256(marker).hexdigest()
        half = len(marker) // 2
        fixtures = {
            'downloads/member-stored-pad.zip': self.zip_bytes_stored({'mk.dat': marker + b'\xff' * 16}),
            'downloads/member-deflate-pad.zip': self.zip_bytes({'mk.dat': marker + b'\xff' * 16}),
            'downloads/member-nul-pad.zip': self.zip_bytes_stored({'mk.dat': marker + b'\x00' * 16}),
            'downloads/member-interior-pad.zip': self.zip_bytes(
                {'mk.dat': marker[:half] + b'\xff' * 16 + marker[half:]}),
            'downloads/member-tar-pad.tar': self.raw_tar([('mk.dat', b'0', marker + b'\xff' * 16)]),
            'downloads/member-gz-expand.zip': self.zip_bytes({'x.dat': gzip.compress(marker + b'\xff' * 16)}),
            'downloads/member-lzma-expand.zip': self.zip_bytes(
                {'x.dat': lzma.compress(marker + b'\xff' * 16, format=lzma.FORMAT_ALONE)}),
            'downloads/assets/theme.css.gz': gzip.compress(marker + b'\xff' * 16),
        }
        for relative, data in fixtures.items():
            with self.subTest(relative=relative):
                path = self.write_binary(relative, data)
                with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
                    with self.assertRaises(privacy.PrivacyViolation):
                        privacy.validate_site(self.root)
                path.unlink()
        benign = self.write_binary('downloads/assets/benign-pad.css.gz',
                                   gzip.compress(b'body{color:navy}' + b'\xff' * 16))
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
            privacy.validate_site(self.root)
        benign.unlink()

    def test_embedded_container_beyond_member_buffer_is_rejected(self):
        marker = self.marker_payload()
        fingerprint = hashlib.sha256(marker).hexdigest()
        inner = self.zip_bytes({'mk.dat': marker})
        tail = b'Z' * 100_000
        big_member = b'A' * (17 * 1024 * 1024) + inner + tail
        control_member = b'A' * (4 * 1024 * 1024) + inner + tail
        fixtures = {
            'downloads/outer-beyond.zip': self.zip_bytes_stored({'blob.bin': big_member}),
            'downloads/outer-beyond.tar': self.raw_tar([('blob.bin', b'0', big_member)]),
        }
        for relative, data in fixtures.items():
            with self.subTest(relative=relative):
                path = self.write_binary(relative, data)
                with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
                    with self.assertRaises(privacy.PrivacyViolation):
                        privacy.validate_site(self.root)
                path.unlink()
        control = self.write_binary('downloads/outer-control.zip',
                                    self.zip_bytes_stored({'blob.bin': control_member}))
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
            with self.assertRaises(privacy.PrivacyViolation):
                privacy.validate_site(self.root)
        control.unlink()
        benign = self.write_binary('downloads/outer-benign.zip',
                                   self.zip_bytes_stored({'blob.bin': b'A' * (17 * 1024 * 1024) + tail}))
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
            privacy.validate_site(self.root)
        benign.unlink()

    def test_utf16_reference_straddling_scan_windows_is_rejected(self):
        straddle = ('loader' + '-' * 4089 + '/src/x.c').encode('utf-16-le')
        short = ('loader' + '-' * 2045 + '/src/x.c').encode('utf-16-le')
        self.write_binary('downloads/utf16-straddle.zip',
                          self.zip_bytes({'blob.bin': b'A' * 57852 + straddle + b'B' * 200_000}))
        with self.assertRaises(privacy.PrivacyViolation):
            privacy.validate_site(self.root)
        (self.root / 'downloads/utf16-straddle.zip').unlink()
        self.write_binary('downloads/utf16-short.zip',
                          self.zip_bytes({'blob.bin': b'A' * 57852 + short + b'B' * 100}))
        with self.assertRaises(privacy.PrivacyViolation):
            privacy.validate_site(self.root)
        (self.root / 'downloads/utf16-short.zip').unlink()
        self.write_binary('docs/utf16-late.dat',
                          b'C' * 17817596 + straddle + b'D' * (2 * 1024 * 1024))
        with self.assertRaises(privacy.PrivacyViolation):
            privacy.validate_site(self.root)
        (self.root / 'docs/utf16-late.dat').unlink()
        self.write_binary('docs/utf16-benign.dat', 'bootloader notes'.encode('utf-16-le') * 4)
        privacy.validate_site(self.root)
        (self.root / 'docs/utf16-benign.dat').unlink()

    def test_ff_padded_signature_fields_are_rejected(self):
        marker = self.marker_payload()
        fingerprint = hashlib.sha256(marker).hexdigest()
        padded_name = marker + b'\xff' * 8
        placeholder = 'n' * len(padded_name)
        tagged_zip = self.zip_bytes({placeholder: b'benign payload\n'}).replace(
            placeholder.encode('ascii'), padded_name)
        fixtures = {
            'downloads/fallback-name-ff.dat': self.truncated_local(name_bytes=padded_name),
            'firmware/valid-name-ff.zip': tagged_zip,
            'downloads/assets/name-ff.css.gz': self.gzip_with_fields(b'body{color:red}', fname=padded_name),
            'downloads/assets/comment-ff.css.gz': self.gzip_with_fields(b'body{color:red}', fcomment=padded_name),
        }
        for relative, data in fixtures.items():
            with self.subTest(relative=relative):
                path = self.write_binary(relative, data)
                with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
                    with self.assertRaises(privacy.PrivacyViolation):
                        privacy.validate_site(self.root)
                path.unlink()
        benign = self.write_binary('downloads/fallback-name-benign-ff.dat',
                                   self.truncated_local(name_bytes=b'p.dat' + b'\xff' * 8,
                                                        payload=b'benign\n', csize=7, fsize=7))
        with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
            privacy.validate_site(self.root)
        benign.unlink()

    def test_confusable_and_double_separator_references_are_rejected(self):
        confusable = 'l\u043eader/src/main.c'
        fixtures = {
            'docs/double-separator.txt': b'see l--oader/src/main.c\n',
            'docs/fullwidth.txt': '\uff4c\uff4f\uff41\uff44\uff45\uff52/src/main.c\n'.encode('utf-8'),
            'docs/confusable.txt': ('see ' + confusable + '\n').encode('utf-8'),
            'data/double-separator.json': json.dumps({'note': 'l--oader/src/main.c'},
                                                     ensure_ascii=False).encode('utf-8'),
            'data/confusable.json': json.dumps({'note': confusable},
                                               ensure_ascii=False).encode('utf-8'),
            'data/confusable-key.json': json.dumps({confusable: 1},
                                                   ensure_ascii=False).encode('utf-8'),
        }
        for relative, data in fixtures.items():
            with self.subTest(relative=relative):
                path = self.write_binary(relative, data)
                with self.assertRaises(privacy.PrivacyViolation):
                    privacy.validate_site(self.root)
                path.unlink()
        self.write_binary('docs/loader-benign.txt', b'bootloader updates; loader diagnostics only\n')
        privacy.validate_site(self.root)
        (self.root / 'docs/loader-benign.txt').unlink()

    def test_native_padding_fingerprint_plus_padding_is_rejected(self):
        marker = self.marker_payload()
        native = marker[:20] + b'\xff' + marker[20:]
        fingerprint = hashlib.sha256(native).hexdigest()
        fixtures = {
            'downloads/native-tail.dat': b'\x00' * 40 + gzip.compress(b'benign-data') + native + b'\xff' * 8,
            'downloads/native-gap.dat': self.zip_with_gap(native + b'\xff' * 8),
        }
        for relative, data in fixtures.items():
            with self.subTest(relative=relative):
                path = self.write_binary(relative, data)
                with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
                    with self.assertRaises(privacy.PrivacyViolation):
                        privacy.validate_site(self.root)
                path.unlink()

    def test_padded_marker_with_trailing_bytes_is_rejected_at_region_sites(self):
        marker = self.marker_payload()
        fingerprint = hashlib.sha256(marker).hexdigest()
        fixtures = {
            'downloads/remainder-suffix.dat': self.truncated_local(
                name_bytes=b'ok.bin', payload=b'benign', csize=6, fsize=6) + marker + b'\xff' * 8 + b'end',
            'downloads/tail-suffix.dat': b'\x00' * 40 + gzip.compress(b'benign-data') + marker + b'\xff' * 8 + b'end',
        }
        for relative, data in fixtures.items():
            with self.subTest(relative=relative):
                path = self.write_binary(relative, data)
                with mock.patch.object(privacy, 'PRIVATE_SOURCE_FINGERPRINTS', {fingerprint}):
                    with self.assertRaises(privacy.PrivacyViolation):
                        privacy.validate_site(self.root)
                path.unlink()


if __name__ == '__main__':
    unittest.main(verbosity=2)
