#!/usr/bin/env python3
"""Independently verify the T147 signed feed and factory before Pages build.

Standard library + OpenSSL only. Never loads a signing/private key.
"""
import base64
import hashlib
import json
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FEED = 'https://projectsape.github.io/ape-firmware-center/firmware/t147-dualboot/update'
BOARD = 'waveshare-esp32-s3-touch-lcd-1.47-lora-dualboot'
LAYOUT = 'ape-t147-dualboot-ota-v2'
TEST_KEY_SHA = '67f66437c0e54cab0723cdca91f40f010aceaa9311160b0d3bfc4a6ef244f4f9'
FIELDS = ('version', 'app_version', 'commit', 'health_protocol', 'board', 'component', 'layout', 'size', 'sha256', 'firmware_url')
SLOTS = {'wadamesh': (0x1a0000, 0x380000, 'wadamesh'), 'meshtastic': (0x520000, 0x400000, 'meshtas')}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def load_json(path):
    return json.loads(path.read_text(), object_pairs_hook=unique_pairs)


def public_path(public, relative):
    require(isinstance(relative, str) and relative and not relative.startswith('/'), 'Invalid public path')
    path = (public / relative).resolve()
    require(path.is_relative_to(public.resolve()), 'Path escapes public directory')
    require(path.is_file(), f'Missing artifact: {relative}')
    return path


def artifact(public, info):
    data = public_path(public, info['file']).read_bytes()
    require(len(data) == info['bytes'] and sha(data) == info['sha256'], f'Artifact integrity mismatch: {info["file"]}')
    return data


def validate_image(data):
    require(len(data) >= 80 and data[0] == 0xe9 and 1 <= data[1] <= 16, 'Invalid ESP image')
    require(struct.unpack_from('<H', data, 12)[0] == 9 and data[23] == 1, 'Expected ESP32-S3 digest image')
    position, checksum = 24, 0xef
    for _ in range(data[1]):
        require(position + 8 <= len(data), 'Truncated segment header')
        _, size = struct.unpack_from('<II', data, position)
        position += 8
        require(size > 0 and position + size <= len(data), 'Truncated image segment')
        for value in data[position:position + size]:
            checksum ^= value
        position += size
    checksum_at = position | 15
    digest_at = checksum_at + 1
    require(digest_at + 32 <= len(data) and data[checksum_at] == checksum, 'ESP checksum mismatch')
    require(hashlib.sha256(data[:digest_at]).digest() == data[digest_at:digest_at + 32], 'ESP digest mismatch')
    require(all(value == 0xff for value in data[digest_at + 32:]), 'Unexpected trailing image data')
    require(struct.unpack_from('<I', data, 32)[0] == 0xabcd5432, 'Missing app descriptor')
    return data[48:80].split(b'\0')[0].decode('ascii')


def validate_manifest(manifest, component):
    require(isinstance(manifest, dict), 'Manifest must be an object')
    require(set(manifest) in (set(FIELDS) | {'schema_version', 'signature'}, set(FIELDS) | {'schema_version', 'signature', 'notes'}), 'Unexpected manifest fields')
    require(type(manifest['schema_version']) is int and manifest['schema_version'] == 3, 'Expected schema 3')
    require(manifest['component'] == component and manifest['board'] == BOARD and manifest['layout'] == LAYOUT, 'Manifest target mismatch')
    require(type(manifest['health_protocol']) is int and manifest['health_protocol'] == 0, 'Unexpected health protocol')
    require(type(manifest['size']) is int and 0 < manifest['size'] <= SLOTS[component][1], 'App exceeds target slot')
    require(re.fullmatch(r'[0-9a-f]{64}', manifest['sha256']) is not None, 'Invalid SHA256')
    require(re.fullmatch(r'[0-9a-f]{40}', manifest['commit']) is not None, 'Invalid source commit')
    for field in ('version', 'app_version'):
        require(isinstance(manifest[field], str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+-]{0,38}', manifest[field]) is not None, 'Invalid app version')
        require('TEST' not in manifest[field].upper() and 'local-ota' not in manifest[field].lower(), 'Test package is not a release')
    name = manifest['firmware_url']
    require(isinstance(name, str) and len(name) <= 96 and re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,95}\.bin', name) is not None and '..' not in name, 'Invalid relative firmware filename')
    lines = ['schema=3']
    for field in FIELDS:
        value = manifest[field]
        require('\n' not in str(value) and '\r' not in str(value), 'Invalid canonical field')
        lines.append(f'{field}={value}')
    return ('\n'.join(lines) + '\n').encode('ascii')


def verify_signature(manifest, canonical, key_path):
    require(isinstance(manifest['signature'], str) and len(manifest['signature']) <= 144, 'Invalid signature length')
    signature = base64.b64decode(manifest['signature'], validate=True)
    require(64 <= len(signature) <= 128, 'Invalid DER signature length')
    with tempfile.TemporaryDirectory() as directory:
        signature_path, payload_path = Path(directory) / 'signature.der', Path(directory) / 'canonical.txt'
        signature_path.write_bytes(signature)
        payload_path.write_bytes(canonical)
        result = subprocess.run(['openssl', 'dgst', '-sha256', '-verify', str(key_path), '-signature', str(signature_path), str(payload_path)], capture_output=True)
        require(result.returncode == 0, 'OTA signature verification failed')


def partition_table(data):
    require(len(data) == 4096, 'Partition reference must be one sector')
    parts = {}
    for position in range(0, len(data), 32):
        magic = struct.unpack_from('<H', data, position)[0]
        if magic == 0xebeb:
            require(data[position + 2:position + 16] == b'\xff' * 14 and hashlib.md5(data[:position]).digest() == data[position + 16:position + 32], 'Partition MD5 mismatch')
            require(data[position + 32:] == b'\xff' * (len(data) - position - 32), 'Partition padding mismatch')
            return parts
        require(magic == 0x50aa, 'Invalid partition entry')
        _, kind, subtype, offset, size, name, flags = struct.unpack_from('<HBBII16sI', data, position)
        name = name.split(b'\0')[0].decode('ascii')
        require(name not in parts and flags == 0, 'Invalid partition name/flags')
        parts[name] = (kind, subtype, offset, size)
    raise ValueError('Missing partition MD5')


def validate(public, catalog):
    active = [x for x in catalog['devices'] if x.get('hardwareGroup') == 't147']
    require({x['id'] for x in active} == {'t147-lora-dualboot', 't147-nolora'} and len(active) == 2, 'Expected exactly two active T147 variants')
    device = next(x for x in active if x['id'] == 't147-lora-dualboot')
    require(not any(x['id'] == 't147-lora' for x in catalog.get('archivedDevices', [])), 'Standalone LoRa is local-only')
    require(not any((public / 'firmware/t147-lora').rglob('*.bin')), 'Standalone LoRa binaries must not be published')
    ota = device['ota']
    require(ota['feedUrl'] == FEED and ota['board'] == BOARD and ota['layout'] == LAYOUT, 'OTA configuration mismatch')
    release = load_json(public_path(public, ota['releaseFile']))
    require(release['board'] == BOARD and release['layout'] == LAYOUT and release['feedUrl'] == FEED, 'Release target mismatch')
    require(set(release['components']) == set(SLOTS) and set(ota['components']) == set(SLOTS), 'Invalid release components')
    key = artifact(public, release['publicKey'])
    require(ota['publicKey'] == release['publicKey']['file'] and b'BEGIN PUBLIC KEY' in key and b'PRIVATE KEY' not in key, 'Invalid public key packaging')
    require(sha(key) != release['publicKey']['testKeySha256'] and sha(key) != TEST_KEY_SHA, 'Bench key is not permitted')
    key_path = public_path(public, ota['publicKey'])
    details = subprocess.run(['openssl', 'pkey', '-pubin', '-in', str(key_path), '-text', '-noout'], capture_output=True, check=True).stdout
    require(b'prime256v1' in details and b'(256 bit)' in details, 'Expected P-256 public key')
    factory = artifact(public, release['factory'])
    require(len(factory) == 0x1000000, 'Factory must be 16MiB')
    loader = artifact(public, release['loader'])
    validate_image(loader)
    require(len(loader) <= 0x180000 and key in loader and FEED.encode() in loader, 'Production loader contract mismatch')
    require(b'APE_TEST ' not in loader and b'APE_RESULT ' not in loader and release['loader']['bench'] is False, 'Bench loader is not permitted')
    require(factory[0x20000:0x20000 + len(loader)] == loader, 'Factory loader differs from USB loader')
    table = artifact(public, release['partitionTable'])
    require(factory[0x8000:0x9000] == table, 'Factory partition reference mismatch')
    expected = {'nvs': (1, 2, 0x9000, 0x4000), 'otadata': (1, 0, 0xd000, 0x2000),
                'wada_nvs': (1, 2, 0xf000, 0x5000), 'tastic_nvs': (1, 2, 0x14000, 0x5000),
                'loader': (0, 0, 0x20000, 0x180000), 'wadamesh': (0, 0x10, 0x1a0000, 0x380000),
                'meshtas': (0, 0x11, 0x520000, 0x400000), 'tiles': (1, 0x83, 0x920000, 0x200000),
                'spiffs': (1, 0x82, 0xb20000, 0x200000), 'tastic_fs': (1, 0x82, 0xd20000, 0x2d0000),
                'coredump': (1, 3, 0xff0000, 0x10000)}
    require(partition_table(table) == expected, 'Unsupported partition layout')
    for name in ('nvs', 'otadata', 'wada_nvs', 'tastic_nvs'):
        _, _, offset, size = expected[name]
        require(factory[offset:offset + size] == b'\xff' * size, 'Factory contains configured NVS')
    update = device['update']
    require(update['eraseAll'] is False and update['requireVerifiedFlashSize'] is True, 'Unsafe USB update policy')
    require(isinstance(update.get('loaderChanged'), bool), 'USB update must declare loaderChanged')
    parts = {part.get('name'): part for part in update['parts']}
    require(len(parts) == len(update['parts']), 'Duplicate USB update part')
    require(set(parts) == set(SLOTS), 'Unexpected USB update parts')
    for component in SLOTS:
        part = parts[component]
        info = release['components'][component]
        require(part['file'] == info['file'] and part['sha256'] == info['sha256'] and int(str(part['offset']), 0) == SLOTS[component][0], 'USB app plan mismatch')
    loader_meta = device.get('loader')
    if update['loaderChanged'] is True:
        require(isinstance(loader_meta, dict), 'loaderChanged requires loader metadata')
    if isinstance(loader_meta, dict):
        require(loader_meta.get('file') == release['loader']['file'] and loader_meta.get('sha256') == sha(loader) and int(str(loader_meta.get('offset')), 0) == 0x20000, 'USB loader metadata mismatch')
    guard = update['requiredLayout']
    require(guard['id'] == LAYOUT and int(str(guard['offset']), 0) == 0x8000 and guard['size'] == 4096 and guard['file'] == release['partitionTable']['file'] and guard['sha256'] == sha(table), 'USB layout guard mismatch')
    require(device['factory']['eraseAll'] is True and len(device['factory']['parts']) == 1, 'Invalid factory plan')
    part = device['factory']['parts'][0]
    require(int(str(part['offset']), 0) == 0 and part['file'] == release['factory']['file'] and part['sha256'] == sha(factory), 'Factory catalog mismatch')
    for component, (offset, capacity, _) in SLOTS.items():
        info = release['components'][component]
        require(info['manifest'] == ota['components'][component]['manifest'], 'OTA manifest catalog mismatch')
        for metadata in (info, ota['components'][component]):
            require(int(metadata['offset'], 0) == offset and int(metadata['slotSize'], 0) == capacity, 'App slot mismatch')
        path = public_path(public, info['manifest'])
        require(path.stat().st_size <= 2048, 'Manifest exceeds loader capacity')
        manifest = load_json(path)
        verify_signature(manifest, validate_manifest(manifest, component), key_path)
        require(public_path(public, info['file']) == (path.parent / manifest['firmware_url']).resolve(), 'Manifest firmware path mismatch')
        data = artifact(public, info)
        require(len(data) == manifest['size'] and sha(data) == manifest['sha256'], 'Manifest app integrity mismatch')
        require(validate_image(data) == info['espAppVersion'], 'Descriptor version mismatch')
        require(factory[offset:offset + len(data)] == data, 'Factory app differs from OTA app')
        provenance = device['provenance'][component]
        require(provenance['version'] == info['version'] == manifest['app_version'] and provenance['commit'] == info['commit'] == manifest['commit'], 'App provenance mismatch')
    require('sourceArtifacts' not in release, 'Build source download metadata is not permitted')
    for provenance in device['provenance'].values():
        require(not (set(provenance) & {'sourceArtifact', 'sourceSha256', 'sourceArchive'}),
                'Build source download metadata is not permitted')
    return True


def main():
    try:
        validate(ROOT / 'public', load_json(ROOT / 'public/data/firmware-catalog.json'))
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as error:
        print('DO NOT DEPLOY — OTA release validation failed:', error)
        return 1
    print('SIGNED OTA + FACTORY + USB GUARDS VALIDATION PASSED')
    return 0


if __name__ == '__main__':
    sys.exit(main())
