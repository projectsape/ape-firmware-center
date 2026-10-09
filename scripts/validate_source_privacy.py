#!/usr/bin/env python3
"""Block public packaging of the independent APE T147 loader source.

Only the Python standard library is used. Archives are streamed and inspected
in memory; this validator never extracts archive members to the filesystem.
"""
import argparse
import bz2
import gzip
import hashlib
import io
import json
import lzma
import os
import re
import stat
import struct
import tarfile
import unicodedata
import zipfile
import zlib
from pathlib import Path, PureWindowsPath
from typing import NoReturn

ROOT = Path(__file__).resolve().parent.parent

# Fingerprints for loader C/C++ files of at least 128 bytes from the private
# snapshots. Only digests are stored here; no loader source text is included.
PRIVATE_SOURCE_FINGERPRINTS = frozenset({
    '071eb0993b8d487a8510c3d991d4afd75fe275693caef7cb51962bfd3e59d9f6',
    '0fa9a3b39523b1bc6eef4f7efd4f1c74ad9cf68197dbbb6ada3c6323f6972c6c',
    '123fe5795a6508403e7ba20ae7d641daa2ef26ae5947ec56f1cd5a5ce96e0066',
    '12f89980b5f701bc52f1dd0699519612adc045a915f77d58f4f93115a3bbdce6',
    '15aead8da73551e84ad64d9daf6481c452a9c7e87c01083be2053ddfb22326cb',
    '17cccfc3f62d22a6cb23fab0eb5e78099cb40dd26aa2768ed811eb9c41c529bc',
    '1932557be4d5b631eda4d601b444ff6097ed5be3d76e59b624f54ce9ac5903a6',
    '1cf4d9f39193792b5481d0dadaa583944dbeaf40a3f9edd88f02d475fadba6c5',
    '207dfef1405359e34dbd38f9d2dbf17692bcda92d27acf7aec3635674d7e239e',
    '32481ce628f27a8b4a716c6e987cb77656b71801f17eeaa78f4d3ee8820552ba',
    '3968c6b01802371de7ec4a98caa51cb6f46ac333f8d79b7e884cf575192ac490',
    '3b83a0d39aebc919e8f35afa3d3ee5ab9faed93abac2687e57bca5fd9e41cdfc',
    '46b12654ac6b223797d2d670c695610d105bd2c9288044607cc871f13991d692',
    '493fde83f28c336bac413637e68e9e68666a2e8f654321b3478d3a25e1788609',
    '4960872e9b5283c723e383d62e79bf89f8f7ef03517d220a0d97f38baa98b623',
    '4a589a1fccb455937d4901560439d922ab675229ee6c8d2bea6df0bbe884770d',
    '4c59ffb0785c138af0b04c9ccbfe36f88bf4d7f64497f923290ebdc6b01fb84c',
    '4dce8af9f7be33cf90e8b9eaa0e6e6686fe1a45f05c004b59995c883f44c1ac9',
    '55e66ef64b2437fd39984995fe589a9ad1f3dc4586251140fac1f0bb0ce85565',
    '5aff1af1a6ce8c78389d802de0b2b2c9babd784ca7ef7786f906adde9e8d6c05',
    '6192fa26468488b3687685a433e60271abd38e2eddaeed64909ae45701cf68e1',
    '64c958b4ac64d4120cdd3af9d9635d4fdac3da5c720a33cbcdcf9ba0b8f2f741',
    '6bbf23d78174394e06c3acad4eaeed16ab85a1e326a17e6bdcb771b74242fa3c',
    '769bb267d46c7766b42f3599de3956b7c1f18b32bf3747ebbfbb11f73f9e3fcf',
    '7b892a8aa8f3fd0674a5f1529d3d6137eef95f8ed557de0de52dc03e9a34e29e',
    '84849ce30a4b6a84c966705f4bf1a88566ec8a27a09173c2fb14da5446edfee5',
    '875f5d8a362cd8747700f5dae1a7ba9ffa8e4d0a4e98fc30e62e22f11c815749',
    '8a9eb01fccc2b944bca41f0d4e34b5539db78138ed3dc609c5412db99f50040b',
    '8d03fdf7073f4350d3ad650ce6ccecef22c3aad5bdd08e1be1e08893f3ebd042',
    '91b9fad15797e3b6ec48784e8162b2e5633be50adec4ca67cba05a6e3b01b939',
    '92f513a3d7f1bab659b77b3877206b0064a8c8c30b218a0dede181f9df16e3f5',
    '948b6f8ab0a7c387a9c342a3d5ce257636e5c1c5cb2972b201b10c6ddcf8cb12',
    '957ccdd5e626b07ecb078cdc00c974e54ddfa80c7eb9dc640d06fcd92aa782c5',
    '9914185fe689c3c6712859091e2909eb4379ac84d6b09f1a472f137bac1e307b',
    'a644f3dde90a6fe4a94a65476209586ffcf90748c76bb089f598e60fe321d000',
    'aa6483de7e5520b797cb6326361dbf21703e8d9bb2fad31ccc6724600b0a79a3',
    'aca59752aa9d04f9a828cbbee40a994a00010855452883cc0eec10336ef47ad0',
    'b083eacfe17201ec73e5d61fa31ccc1f7cdaf03e357499382e64a26c377c6382',
    'b0d3b3ac474c6f6faed2077cb3bcf38e7a7703c377812fbc33cfd8cc0a103621',
    'b87aea9da8c4bc103a9a58fca670c739f83df0f005c41916af28441363210e25',
    'bc86533d55c16294d8e7efc2df1c761f26b46271f423685545c6bddd2a569d05',
    'c5d3cc2ef186a977853b25e9dee35d3ab182b98149b8a954eb1e998dbf4a7fad',
    'c6c95186fe6320476ebc076e0d0b04d6e28b866797a2a76fcfb8fcaca36cbe14',
    'cb209092abc601f6f0cc553c26768a009e68789a261b0586f9bee27cd8eee4a4',
    'd6b72fd571bbf49dcc8a022b07a8cdeb7581033b49a977a68c7ec786b852c0ff',
    'd8f29981697afd699c7b4dc092b2d2d9138e61f39a9d7574e151a8378a8e8310',
    'dbccfacf2fb00c5ac51ef808607a4a9c91ced818e4530db359d73a20b61e1fa4',
    'dfcf3c3303854d2c962a062d35cd046c72f0ba0575779474479d5f08e8ddeefd',
    'e01fc04099db3250bda029dbadea3b7188e5de8fc321b5e7434060a0594f4943',
    'e0c4e943e6c0ff90cc46dd29feffe4068fe9a95e133660a94c19bb4071476e7c',
    'e20b4c8cf1cac3b94eb4d8057f88756647a2c14000a4ab116d3aad620af9e5fc',
    'e5f928a69bf2d783017b05bcde69e7b9cac653a62a23c0fc413c389a71ef4a9e',
    'e7f8e2d9b22bd5d017b864fa189116189dee93f6ec3ecbf683cf42ae0626f55c',
    'e8021831461f02e3865557ee3966aad769781992881521ec1e0a57275b39a8fa',
    'edb5d609188bdeffce49a4eba65b6fbcb76f14a09bba08bdaa2c49a000db86b',
    'f2a0caed2df44a2caf492f685e26042134b2541927c68e5b07556128fc08b17d',
    'f97ec6fde7da8fb2418862145117382496d4e2cafcdfb76e1686db436ba17727',
    'f9bd7082153dc6ada73f5956fe8ebfd6670a44e50c36b340b658f7e8923fda31',
    'fa5a9681368c3c3138eaa3714707feaefbfc5ad7fe8cd46cb407c81b0510db7f',
})

MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_CONTENT_BYTES = 256 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 20_000
MAX_ARCHIVE_MEMBER_BYTES = 128 * 1024 * 1024
MAX_ARCHIVE_DEPTH = 4
MAX_TAR_EXTENDED_HEADER_BYTES = 4096
MAX_TAR_EXTENDED_HEADER_CHAIN = 64
MAX_RAW_SOURCE_BYTES = 16 * 1024 * 1024
MAX_FINGERPRINT_FILE_BYTES = 16 * 1024 * 1024
MAX_SITE_FINGERPRINT_BYTES = 512 * 1024 * 1024
MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_JSON_DEPTH = 128
MAX_SYMLINK_TARGET_BYTES = 4096
MAX_COMPRESSED_MEMBERS = 1024
MAX_DECOMPRESS_CHUNK = 1024 * 1024
MAX_EMBEDDED_CANDIDATES = 256
MAX_EMBEDDED_PROBE_BYTES = 64 * 1024
MAX_EMBEDDED_SCAN_BYTES = 16 * 1024 * 1024
MAX_UNINSPECTED_REGIONS = 65_536
MAX_UNINSPECTED_REGION_BYTES = 8 * 1024 * 1024
MAX_INCOMPLETE_CONTAINER_BYTES = 8 * 1024 * 1024
MAX_TEXT_SCAN_BYTES = 16 * 1024 * 1024
MAX_REGION_PROBE_RUNS = 100_000
MAX_LZMA_PROBE_BYTES = 1024 * 1024
MAX_TAR_CHECKSUM_OFFSETS = 512
_MAX_SEPARATOR_RUN = 4096
_MAX_SEPARATOR_BYTES = 4
# The chunked scans must overlap by at least the widest possible match: a
# reference word plus a run of up to _MAX_SEPARATOR_RUN separators (each one
# up to _MAX_SEPARATOR_BYTES wide) may never straddle two windows, including
# the NUL-interleaved UTF-16 rescan where every byte is doubled.
_TEXT_SCAN_OVERLAP = 2 * (_MAX_SEPARATOR_RUN * _MAX_SEPARATOR_BYTES + 256)
# Best-effort cap for the run walk on the large sites that skip the shared
# probe budget; the walk stops silently past the cap so a legitimate region
# can never be rejected by it.
_MAX_UNBUDGETED_PROBE_RUNS = 4096
_EMBEDDED_STREAM_LOOKBACK = 512
_MAX_EMBEDDED_STREAM_COLLECT = 2 * MAX_EMBEDDED_SCAN_BYTES
CONTAINER_START_BYTES = 16
EMBEDDED_SIGNATURES = (
    (b'PK\x03\x04', 'zip'),
    (b'PK\x05\x06', 'zip'),
    (b'\x1f\x8b\x08', 'gzip'),
    (b'\xfd7zXZ\x00', 'xz'),
    (b'BZh', 'bzip2'),
    (b'7z\xbc\xaf\x27\x1c', '7z'),
    (b'Rar!\x1a\x07', 'rar'),
    (b'\x28\xb5\x2f\xfd', 'zstd'),
    (b'\x04\x22\x4d\x18', 'lz4'),
)
SKIPPABLE_FRAME_TAIL = b'\x2a\x4d\x18'
SKIPPABLE_FRAME_KIND = 'skippable'
PRIVATE_TEXT_PATTERNS = (
    b'loader-source',
    b'loader_source',
    b'loader/src',
    b'loader\\src',
    b'loader/include',
    b'loader\\include',
)
LZMA_ALONE_DICTIONARY_SIZES = frozenset(
    {1 << shift for shift in range(12, 29)} | {0xFFFFFFFF})
UNINSPECTABLE_CONTAINERS = frozenset({'7z', 'rar', 'zstd', 'lz4', 'skippable'})
COMPRESSED_KINDS = frozenset({'gzip', 'bzip2', 'xz', 'lzma'})
NATIVE_SOURCE_SUFFIXES = frozenset({
    '.c', '.cc', '.cpp', '.cxx', '.c++', '.h', '.hh', '.hpp', '.hxx',
    '.ino', '.ipp', '.tpp', '.inc', '.s', '.asm',
})
ARCHIVE_SUFFIXES = (
    '.tar.gz', '.tar.bz2', '.tar.xz', '.tbz2', '.tgz', '.tbz', '.txz',
    '.tar', '.zip', '.7z', '.rar', '.tar.zst', '.tzst', '.zst',
    '.gz', '.bz2', '.xz', '.lzma',
)
SUPPORTED_ARCHIVE_SUFFIXES = frozenset({
    '.tar.gz', '.tar.bz2', '.tar.xz', '.tbz2', '.tgz', '.tbz', '.txz',
    '.tar', '.zip', '.gz', '.bz2', '.xz', '.lzma',
})
# Separator-tolerant spelling: letters may be split by a bounded separator run
# (the expressions below allow runs between letters AND between words), so
# 'l--oader source-x', 'l--oader/src', leet spellings and unicode dashes are
# all covered while the chunked text scan cannot miss a match at a window
# boundary; no separate collapse pass is needed.
_TEXT_SEPARATOR = r'[\s\-_/\\:.]'
_TEXT_SEPARATOR_RUN = rf'{_TEXT_SEPARATOR}{{0,{_MAX_SEPARATOR_RUN}}}'
_LOADER_WORD = (r'[l1]' + _TEXT_SEPARATOR_RUN + r'[o0]' + _TEXT_SEPARATOR_RUN + r'[a4]'
                + _TEXT_SEPARATOR_RUN + r'd' + _TEXT_SEPARATOR_RUN + r'[e3]'
                + _TEXT_SEPARATOR_RUN + r'r')
_SOURCE_WORD = (r'[s5]' + _TEXT_SEPARATOR_RUN + r'[o0]' + _TEXT_SEPARATOR_RUN + r'u'
                + _TEXT_SEPARATOR_RUN + r'r' + _TEXT_SEPARATOR_RUN + r'c'
                + _TEXT_SEPARATOR_RUN + r'[e3]')
PRIVATE_ARCHIVE_NAME = re.compile(
    rf'{_LOADER_WORD}{_TEXT_SEPARATOR_RUN}{_SOURCE_WORD}[-_]?', re.IGNORECASE)
PRIVATE_ARCHIVE_REFERENCE = re.compile(
    rf'{_LOADER_WORD}{_TEXT_SEPARATOR_RUN}{_SOURCE_WORD}[-_/]?', re.IGNORECASE)
PRIVATE_LAYOUT_REFERENCE = re.compile(
    rf'{_LOADER_WORD}{_TEXT_SEPARATOR_RUN}(?:src|include)[/\\]', re.IGNORECASE)
_BYTE_SEPARATOR = rb'(?:[\s\-_/\\:.]|[\xc2-\xf4][\x80-\xbf]{1,3})'
_BYTE_SEPARATOR_RUN = _BYTE_SEPARATOR + f'{{0,{_MAX_SEPARATOR_RUN}}}'.encode('ascii')
# Round 6: each letter class also accepts the common Cyrillic/Greek
# confusables and the fullwidth forms (both cases), so 'lоader/src' matches
# directly without any normalisation pass.
_BYTE_CONFUSABLES = {
    'l': ('ｌ', 'Ｌ'),
    'o': ('о', 'О', 'ο', 'Ο', 'ｏ', 'Ｏ'),
    'a': ('а', 'А', 'α', 'Α', 'ａ', 'Ａ'),
    'd': ('ԁ', 'Ԁ', 'ｄ', 'Ｄ'),
    'e': ('е', 'Е', 'ε', 'Ε', 'ｅ', 'Ｅ'),
    'r': ('р', 'Р', 'ρ', 'Ρ', 'ｒ', 'Ｒ'),
    's': ('ѕ', 'Ѕ', 'σ', 'Σ', 'ｓ', 'Ｓ'),
    'u': ('υ', 'Υ', 'ｕ', 'Ｕ'),
    'c': ('с', 'С', 'ｃ', 'Ｃ'),
    'i': ('і', 'І', 'ι', 'Ι', 'ｉ', 'Ｉ'),
    'n': ('ｎ', 'Ｎ'),
}


def _byte_letter(ascii_class, key):
    parts = [ascii_class]
    for character in _BYTE_CONFUSABLES.get(key, ()):
        parts.append(re.escape(character.encode('utf-8')))
    return rb'(?:' + rb'|'.join(parts) + rb')'


_LOADER_BYTES = (_byte_letter(rb'[l1]', 'l') + _BYTE_SEPARATOR_RUN
                 + _byte_letter(rb'[o0]', 'o') + _BYTE_SEPARATOR_RUN
                 + _byte_letter(rb'[a4]', 'a') + _BYTE_SEPARATOR_RUN
                 + _byte_letter(rb'd', 'd') + _BYTE_SEPARATOR_RUN
                 + _byte_letter(rb'[e3]', 'e') + _BYTE_SEPARATOR_RUN
                 + _byte_letter(rb'r', 'r'))
_SOURCE_BYTES = (_byte_letter(rb'[s5]', 's') + _BYTE_SEPARATOR_RUN
                 + _byte_letter(rb'[o0]', 'o') + _BYTE_SEPARATOR_RUN
                 + _byte_letter(rb'u', 'u') + _BYTE_SEPARATOR_RUN
                 + _byte_letter(rb'r', 'r') + _BYTE_SEPARATOR_RUN
                 + _byte_letter(rb'c', 'c') + _BYTE_SEPARATOR_RUN
                 + _byte_letter(rb'[e3]', 'e'))
_SRC_BYTES = (_byte_letter(rb's', 's') + _BYTE_SEPARATOR_RUN
              + _byte_letter(rb'r', 'r') + _BYTE_SEPARATOR_RUN
              + _byte_letter(rb'c', 'c'))
_INCLUDE_BYTES = (_byte_letter(rb'i', 'i') + _BYTE_SEPARATOR_RUN
                  + _byte_letter(rb'n', 'n') + _BYTE_SEPARATOR_RUN
                  + _byte_letter(rb'c', 'c') + _BYTE_SEPARATOR_RUN
                  + _byte_letter(rb'l', 'l') + _BYTE_SEPARATOR_RUN
                  + _byte_letter(rb'u', 'u') + _BYTE_SEPARATOR_RUN
                  + _byte_letter(rb'd', 'd') + _BYTE_SEPARATOR_RUN
                  + _byte_letter(rb'e', 'e'))
PRIVATE_REFERENCE_BYTES = re.compile(
    _LOADER_BYTES + _BYTE_SEPARATOR_RUN + _SOURCE_BYTES + rb'[-_/]?'
    rb'|' + _LOADER_BYTES + _BYTE_SEPARATOR_RUN
    + rb'(?:' + _SRC_BYTES + rb'|' + _INCLUDE_BYTES + rb')[/\\]',
    re.IGNORECASE,
)
PADDING_RUN = re.compile(rb'[\x00\xff]+')
# Cheap marker bytes that can start a Cyrillic/Greek/fullwidth confusable.
# Probes around these positions keep the confusable pass almost free on
# ordinary windows (the tolerant expression only runs on bounded slices).
_CONFUSABLE_MARKERS = (b'\xd0', b'\xd1', b'\xd2', b'\xd3', b'\xd4', b'\xce', b'\xcf',
                       b'\xef\xbc', b'\xef\xbd')
_MAX_CONFUSABLE_PROBES = 16
_CONFUSABLE_SLICE_BYTES = 1024


def _confusable_slices(window):
    """Bounded slices around possible confusable spellings (round 6)."""
    positions = []
    for marker in _CONFUSABLE_MARKERS:
        start = 0
        while len(positions) < _MAX_CONFUSABLE_PROBES:
            position = window.find(marker, start)
            if position < 0:
                break
            positions.append(position)
            start = position + 1
    for position in sorted(positions):
        yield window[max(0, position - 16):position + _CONFUSABLE_SLICE_BYTES]
_EMBEDDED_STREAM_SCAN = re.compile(
    b'|'.join(re.escape(magic) for magic, _label in EMBEDDED_SIGNATURES))
# Round 6: Cyrillic/Greek confusables for the letters that spell the protected
# words, plus the fullwidth ASCII block; folded to ASCII before the tolerant
# scans run so 'lоader/src' or 'ｌｏａｄｅｒ' cannot dodge detection.
_ASCII_CONFUSABLES = {
    'о': 'o', 'а': 'a', 'е': 'e', 'с': 'c', 'р': 'p', 'х': 'x', 'у': 'y',
    'і': 'i', 'ѕ': 's', 'ј': 'j', 'к': 'k', 'м': 'm', 'т': 't', 'в': 'b',
    'н': 'h', 'ԁ': 'd',
    'ο': 'o', 'α': 'a', 'ε': 'e', 'ι': 'i', 'ν': 'v', 'ρ': 'p', 'τ': 't',
    'υ': 'u', 'σ': 's',
}
_DIGIT_HOMOGLYPHS = str.maketrans({'0': 'o', '1': 'l', '3': 'e', '4': 'a', '5': 's', '7': 't'})
_BYTE_LEET_TABLE = bytes.maketrans(b'013457', b'oleast')
_HINT_SEPARATOR_DELETE = b' \t\n\r\f\v-_/\\:.' + bytes(range(0x80, 0x100))
_LZMA_ALONE_DICTIONARY_PATTERNS = tuple(
    struct.pack('<I', size) for size in sorted(LZMA_ALONE_DICTIONARY_SIZES))
_LZMA_ALONE_HINT = re.compile(
    b'\x5d(?:' + b'|'.join(re.escape(pattern) for pattern in _LZMA_ALONE_DICTIONARY_PATTERNS) + b')')


class PrivacyViolation(ValueError):
    """Raised when a public tree contains private-loader source or metadata."""


class InspectionError(PrivacyViolation):
    """Raised when a candidate container cannot be parsed; still fails closed at the top level."""


class UnsafeStream(PrivacyViolation):
    """Raised when a declared container is truncated or corrupt after producing content."""


def _fail(message) -> NoReturn:
    raise PrivacyViolation(message)


class _InspectionBudget:
    def __init__(self):
        self.content_bytes = 0
        self.members = 0
        self.region_probe_runs = 0

    def consume_content(self, amount):
        self.content_bytes += amount
        if self.content_bytes > MAX_ARCHIVE_CONTENT_BYTES:
            _fail('Archive exceeds the total inspected content limit')

    def consume_members(self, amount):
        self.members += amount
        if self.members > MAX_ARCHIVE_MEMBERS:
            _fail('Archive exceeds the total member-count limit')

    def consume_region_probe_runs(self, amount):
        self.region_probe_runs += amount
        if self.region_probe_runs > MAX_REGION_PROBE_RUNS:
            _fail('Container declares too many padding-separated regions to audit safely')


def _sha256_stream(stream, maximum=None):
    digest = hashlib.sha256()
    total = 0
    while True:
        chunk_size = 64 * 1024
        if maximum is not None:
            chunk_size = min(chunk_size, maximum - total + 1)
        chunk = stream.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if maximum is not None and total > maximum:
            _fail('Source-like file exceeds the inspection size limit')
        digest.update(chunk)
    return digest.hexdigest(), total


def _check_private_digest(digest, description):
    if digest in PRIVATE_SOURCE_FINGERPRINTS:
        _fail(f'Private loader source fingerprint found in {description}')


def _check_padded_fingerprint_variants(field, description):
    """Detect padded or split copies of a private fingerprint (round 6, SC5-1/SC5-4).

    Two extra spellings of the field are compared against the fingerprints:
    the field with every 0x00/0xFF byte removed (covers padding at the ends,
    interior padding and mixed 0x00/0xFF padding) and the field with only the
    leading/trailing 0x00/0xFF bytes removed (covers a fingerprint that itself
    contains 0x00/0xFF bytes and was padded around them).
    """
    if b'\x00' not in field and b'\xff' not in field:
        return
    compacted = field.translate(None, b'\x00\xff')
    if compacted and compacted != field:
        _check_private_digest(hashlib.sha256(compacted).hexdigest(), description)
    trimmed = field.strip(b'\x00\xff')
    if trimmed and trimmed != field and trimmed != compacted:
        _check_private_digest(hashlib.sha256(trimmed).hexdigest(), description)


def _check_region_fingerprints(region, description, budget=None, probe_runs=True):
    """Audit a byte region that no structural parser covers.

    Four variants are compared against the private fingerprints at every call
    site: the exact digest, the digest after removing every 0x00/0xFF padding
    byte (so markers padded at the ends, split by padding runs or mixed with
    0x00/0xFF padding are detected, at any region size and without touching
    the probe budget), the digest after removing only the leading/trailing
    padding bytes (so a fingerprint that itself contains 0x00/0xFF is caught
    too) and the digests of padding-separated runs.

    The run walk is incremental: bounded by the archive-wide probe budget
    where ``probe_runs`` is enabled, and by a small local cap on the sites
    that skip that budget (silently stopped past the cap, so a legitimate
    large region can never be failed closed by the walk). The walk is skipped
    entirely when the region contains no padding byte.
    """
    if not region:
        return
    _check_private_digest(hashlib.sha256(region).hexdigest(), description)
    if b'\x00' not in region and b'\xff' not in region:
        return
    _check_padded_fingerprint_variants(region, description)
    if budget is None:
        return
    cursor = 0
    runs = 0
    for match in PADDING_RUN.finditer(region):
        if match.start() > cursor:
            runs += 1
            if probe_runs:
                budget.consume_region_probe_runs(1)
            elif runs > _MAX_UNBUDGETED_PROBE_RUNS:
                return
            _check_private_digest(hashlib.sha256(region[cursor:match.start()]).hexdigest(),
                                  description)
        cursor = match.end()
    if cursor < len(region):
        runs += 1
        if probe_runs:
            budget.consume_region_probe_runs(1)
        if probe_runs or runs <= _MAX_UNBUDGETED_PROBE_RUNS:
            _check_private_digest(hashlib.sha256(region[cursor:]).hexdigest(), description)


def _audit_signature_bytes(field, description):
    """Digest and text-scan a raw metadata field (name, prefix, link, comment)."""
    if not field:
        return
    stripped = field.rstrip(b'\x00')
    if not stripped:
        return
    _check_private_digest(hashlib.sha256(stripped).hexdigest(), description)
    _check_padded_fingerprint_variants(field, description)
    _scan_private_text(field, description)


def _check_signature_digest(field, description):
    """Digest a raw metadata field without running the tolerant text scan."""
    if not field:
        return
    stripped = field.rstrip(b'\x00')
    if not stripped:
        return
    _check_private_digest(hashlib.sha256(stripped).hexdigest(), description)
    _check_padded_fingerprint_variants(field, description)


def _audit_extra_field(extra, description, budget=None):
    """Audit an extra-field blob, including each well-formed record body."""
    if not extra:
        return
    _check_region_fingerprints(extra, description, budget)
    _scan_private_text(extra, description)
    position = 0
    while position + 4 <= len(extra):
        length = int.from_bytes(extra[position + 2:position + 4], 'little')
        record_end = position + 4 + length
        if record_end > len(extra):
            _fail(f'Container extra field is truncated in {description}')
        record = extra[position:record_end]
        payload = extra[position + 4:record_end]
        _check_private_digest(hashlib.sha256(record).hexdigest(), description)
        _check_region_fingerprints(payload, description, budget)
        _scan_private_text(payload, description)
        position = record_end


def _safe_member_path(name, allow_root_directory=False):
    if not isinstance(name, str) or '\0' in name:
        _fail('Archive contains an invalid member path')
    if len(name) > 4096:
        _fail('Archive member path exceeds the inspection size limit')
    normalized = name.replace('\\', '/')
    if normalized.startswith('/') or PureWindowsPath(normalized).drive:
        _fail('Archive contains an absolute member path')
    parts = []
    for part in normalized.split('/'):
        if part in ('', '.'):
            continue
        if part == '..':
            _fail('Archive member path traverses its root')
        parts.append(part)
    result = '/'.join(parts)
    if not result and not allow_root_directory:
        _fail('Archive contains an empty member path')
    return result


def _safe_link_target(member_path, target, symbolic):
    if not isinstance(target, str) or not target or '\0' in target:
        _fail('Archive contains an invalid link target')
    normalized = target.replace('\\', '/')
    if normalized.startswith('/') or PureWindowsPath(normalized).drive:
        _fail('Archive link target is absolute')
    stack = member_path.split('/')[:-1] if symbolic else []
    for part in normalized.split('/'):
        if part in ('', '.'):
            continue
        if part == '..':
            if not stack:
                _fail('Archive link target escapes its root')
            stack.pop()
        else:
            stack.append(part)


def _is_native_source(path):
    return Path(path).suffix.casefold() in NATIVE_SOURCE_SUFFIXES


def _loader_layout_source(paths):
    branches = set()
    count = 0
    for path in paths:
        parts = _folded_ascii(path).replace('\\', '/').split('/')
        for index, part in enumerate(parts[:-1]):
            if part == 'loader' and index + 1 < len(parts) - 1 and parts[index + 1] in {'src', 'include'}:
                branches.add(parts[index + 1])
                count += 1
                break
    return count >= 12 and branches == {'src', 'include'}


def _parse_tar_octal(field, description):
    if field and field[0] & 0x80:
        _fail(f'TAR uses an unsupported base-256 {description} field')
    value = field.rstrip(b'\0 ').lstrip(b' ')
    if not value:
        return 0
    if any(byte < ord('0') or byte > ord('7') for byte in value):
        _fail(f'TAR has an invalid octal {description} field')
    return int(value, 8)


def _looks_like_tar_header(header):
    if len(header) < 512 or header[:512] == b'\0' * 512:
        return False
    try:
        expected = _parse_tar_octal(header[148:156], 'checksum')
    except PrivacyViolation:
        return False
    check = bytearray(header[:512])
    check[148:156] = b' ' * 8
    unsigned_sum = sum(check)
    signed_sum = sum(byte if byte < 128 else byte - 256 for byte in check)
    return expected in (unsigned_sum, signed_sum)


def _check_tar_extended_header(body, relative, budget):
    for record in body.split(b'\n'):
        if not record:
            continue
        separator = record.find(b' ')
        if separator <= 0 or not record[:separator].isdigit():
            _fail(f'TAR extended header record cannot be parsed in {relative}')
        key, _, value = record[separator + 1:].partition(b'=')
        if not key or not _:
            _fail(f'TAR extended header record cannot be parsed in {relative}')
        _check_region_fingerprints(key, f'TAR extended header key in {relative}', budget)
        _check_region_fingerprints(value, f'TAR extended header in {relative}', budget)
        if key in {b'path', b'linkpath'}:
            target = value.decode('utf-8', 'replace')
            _check_private_name(target, f'TAR extended header in {relative}')
            if _is_loader_source_path(target):
                _fail(f'Private loader source layout found in archive {relative}: {target}')
            _scan_private_text(value, f'TAR extended header in {relative}')
        else:
            _scan_private_text(value, f'TAR extended header in {relative}')


def _check_tar_long_name(body, relative, budget):
    name = body.split(b'\x00', 1)[0]
    if body[len(name):].strip(b'\x00'):
        _fail(f'TAR long name record contains unexpected data in {relative}')
    if b'\n' in name or b'\r' in name:
        _fail(f'TAR long name record contains unexpected data in {relative}')
    target = name.decode('utf-8', 'replace')
    _check_region_fingerprints(body, f'TAR long name in {relative}', budget)
    _check_region_fingerprints(name, f'TAR long name in {relative}', budget)
    _check_private_name(target, f'TAR long name in {relative}')
    if _is_loader_source_path(target):
        _fail(f'Private loader source layout found in archive {relative}: {target}')
    _scan_private_text(name, f'TAR long name in {relative}')


def _preflight_tar(data, relative, budget):
    position = 0
    headers = 0
    extended_chain = 0
    pax_seen = False
    extensions = {b'x', b'g', b'L', b'K'}
    while position + 512 <= len(data):
        header = data[position:position + 512]
        if header == b'\x00' * 512:
            if any(data[position:]):
                _fail('TAR contains nonzero data after its end marker')
            return headers
        if not _looks_like_tar_header(header):
            _fail('TAR contains an invalid header or checksum')

        headers += 1
        if headers > MAX_ARCHIVE_MEMBERS:
            _fail('TAR exceeds the total header/member-count limit')
        kind = header[156:157]
        size = _parse_tar_octal(header[124:136], 'size')
        if kind in extensions:
            extended_chain += 1
            if extended_chain > MAX_TAR_EXTENDED_HEADER_CHAIN:
                _fail('TAR extended-header chain exceeds its count limit')
            if size > MAX_TAR_EXTENDED_HEADER_BYTES:
                _fail('TAR extended header exceeds its per-header size limit')
        else:
            extended_chain = 0

        payload_start = position + 512
        payload_end = payload_start + size
        next_position = payload_start + ((size + 511) // 512) * 512
        if next_position > len(data) or payload_end > len(data):
            _fail('TAR header payload exceeds the bounded archive content')
        # Round 4: digest and scan the raw header fields, so that a PAX path
        # override or a windowed name/prefix field cannot hide private bytes.
        _check_signature_digest(header[0:100], f'TAR member name field in {relative}')
        _check_signature_digest(header[345:500], f'TAR member prefix field in {relative}')
        _check_signature_digest(header[157:257], f'TAR link name field in {relative}')
        _scan_private_text(header[0:100] + header[345:500] + header[157:257],
                           f'TAR header in {relative}')
        raw_name = header[0:100].split(b'\x00', 1)[0]
        raw_prefix = header[345:500].split(b'\x00', 1)[0]
        raw_path = raw_prefix + b'/' + raw_name if raw_prefix else raw_name
        if raw_path and b'oader' in raw_path.lower():
            raw_path_text = raw_path.decode('utf-8', 'replace')
            _check_private_name(raw_path_text, f'TAR raw member name in {relative}')
            if _is_loader_source_path(raw_path_text):
                _fail(f'Private loader source layout found in archive {relative}: {raw_path_text}')
        body = data[payload_start:payload_end]
        if kind in extensions or pax_seen:
            # Raw/parsed divergence is only possible after an extended header:
            # digest the bytes the raw walk covers.
            _check_region_fingerprints(body, f'TAR member body in {relative}', budget,
                                       probe_runs=False)
        if kind in {b'x', b'g'}:
            pax_seen = True
            _scan_private_text(body, f'TAR extended header in {relative}')
            _check_tar_extended_header(body, relative, budget)
        elif kind in {b'L', b'K'}:
            _check_tar_long_name(body, relative, budget)
        if data[payload_end:next_position].strip(b'\x00'):
            _fail('TAR member padding contains unexpected data')
        position = next_position

    if position != len(data):
        _fail('TAR ends with a truncated header block')
    return headers


def _kind_from_header(name, header):
    folded = name.casefold()
    recognized_suffix = next((suffix for suffix in ARCHIVE_SUFFIXES if folded.endswith(suffix)), None)
    if recognized_suffix and recognized_suffix not in SUPPORTED_ARCHIVE_SUFFIXES:
        _fail(f'Unsupported archive format in public tree: {name}')
    if recognized_suffix == '.zip' or header.startswith((b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08')):
        return 'zip'
    if header.startswith((b'7z\xbc\xaf\x27\x1c', b'Rar!\x1a\x07', b'\x28\xb5\x2f\xfd', b'\x04\x22\x4d\x18')):
        _fail(f'Unsupported compressed archive format in public tree: {name}')
    if header.startswith(b'\x1f\x8b'):
        return 'gzip'
    if header.startswith(b'BZh'):
        return 'bzip2'
    if header.startswith(b'\xfd7zXZ\x00'):
        return 'xz'
    if _looks_like_tar_header(header):
        return 'tar'
    if recognized_suffix in {'.gz', '.bz2', '.xz', '.lzma'}:
        return {'.gz': 'gzip', '.bz2': 'bzip2', '.xz': 'xz', '.lzma': 'lzma'}[recognized_suffix]
    if recognized_suffix:
        return 'tar'
    return None


def _is_loader_source_path(name):
    parts = _folded_ascii(name).replace('\\', '/').split('/')
    return _is_native_source(name) and 'loader' in parts[:-1]


def _consume_regular_member(stream, name, size, relative, seen, loader_paths,
                            depth, budget, already_charged):
    if size < 0 or size > MAX_ARCHIVE_MEMBER_BYTES:
        _fail('Archive member exceeds the inspection size limit')
    if name in seen:
        _fail('Archive contains duplicate normalized member paths')
    seen.add(name)
    if _is_loader_source_path(name):
        _fail(f'Private loader source layout found in archive {relative}: {name}')
    if _is_native_source(name):
        loader_paths.append(name)

    digest = hashlib.sha256()
    compacted_digest = None
    total = 0
    nested_chunks = None
    buffered = bytearray()
    text_tail = b''
    # Round 6 (SC5-1): a lazily-started digest of the content with every
    # 0x00/0xFF byte removed detects padded copies of a fingerprint. Until the
    # first padding byte appears the filtered stream equals the exact one, so
    # padding-free members pay no extra hashing.
    scan_tail = None
    collected = None
    collected_from = 0
    collect_overflow = False

    def extend_collected(portion):
        nonlocal collect_overflow
        if collect_overflow or collected is None:
            return
        collected.extend(portion)
        if len(collected) > _MAX_EMBEDDED_STREAM_COLLECT:
            collect_overflow = True
            del collected[_MAX_EMBEDDED_STREAM_COLLECT:]

    def probe_embedded(portion, portion_start):
        # Round 6 (SC5-2): content beyond the embedded-scan buffer is watched
        # in a rolling window; the first container signature starts the
        # collection of the remaining bytes so a candidate past the buffer is
        # inspected in full instead of being silently truncated away.
        nonlocal scan_tail, collected, collected_from, collect_overflow
        if scan_tail is None:
            scan_tail = bytes(buffered[-_EMBEDDED_STREAM_LOOKBACK:])
        if collected is not None:
            extend_collected(portion)
            return
        window = scan_tail + portion
        hit = _embedded_stream_hit(window)
        if hit is not None:
            collected_from = portion_start - len(scan_tail) + hit
            collected = bytearray(window[hit:])
            if len(collected) > _MAX_EMBEDDED_STREAM_COLLECT:
                collect_overflow = True
                del collected[_MAX_EMBEDDED_STREAM_COLLECT:]
            return
        scan_tail = window[-_EMBEDDED_STREAM_LOOKBACK:]

    def consume(chunk):
        nonlocal total, nested_chunks, text_tail, compacted_digest
        start = total
        total += len(chunk)
        if total > size or total > MAX_ARCHIVE_MEMBER_BYTES:
            _fail('Archive member exceeds its declared size or inspection limit')
        if not already_charged:
            budget.consume_content(len(chunk))
        # Round 5 (SC4-WIN): text-scan the member content itself, streaming
        # with overlap, so references are covered beyond the container window.
        if text_tail or b'l' in chunk or b'L' in chunk or b'1' in chunk:
            window = text_tail + chunk
            _scan_private_text(window, f'archive member in {relative}')
            text_tail = window[-_TEXT_SCAN_OVERLAP:]
        if b'\x00' in chunk or b'\xff' in chunk:
            if compacted_digest is None:
                compacted_digest = digest.copy()
            compacted_digest.update(chunk.translate(None, b'\x00\xff'))
        if nested_chunks is None and _kind_from_header(name, chunk[:512]) is not None:
            nested_chunks = []
        if nested_chunks is not None:
            nested_chunks.append(chunk)
        elif len(buffered) < MAX_EMBEDDED_SCAN_BYTES:
            take = min(len(chunk), MAX_EMBEDDED_SCAN_BYTES - len(buffered))
            buffered.extend(chunk[:take])
            if take < len(chunk):
                probe_embedded(chunk[take:], start + take)
        else:
            probe_embedded(chunk, start)
        digest.update(chunk)

    prefix_target = min(512, size)
    prefix_parts = []
    prefix_size = 0
    while prefix_size < prefix_target:
        chunk = stream.read(prefix_target - prefix_size)
        if not chunk:
            break
        prefix_parts.append(chunk)
        prefix_size += len(chunk)
    if prefix_size != prefix_target:
        _fail('Archive member ended before its declared size')
    if prefix_parts:
        consume(b''.join(prefix_parts))

    while True:
        chunk = stream.read(64 * 1024)
        if not chunk:
            break
        consume(chunk)

    if total != size:
        _fail('Archive member size does not match its content')
    _check_private_digest(digest.hexdigest(), f'archive in {relative}')
    if compacted_digest is not None:
        _check_private_digest(compacted_digest.hexdigest(), f'archive in {relative}')
    if nested_chunks is None and buffered and len(buffered) == total:
        trimmed = bytes(buffered).strip(b'\x00\xff')
        if trimmed and len(trimmed) != len(buffered):
            _check_private_digest(hashlib.sha256(trimmed).hexdigest(), f'archive in {relative}')
    if nested_chunks is None:
        try:
            if not stream.seekable():
                _fail(f'Cannot safely inspect non-seekable archive member for embedded ZIP in {relative}')
            position = stream.tell()
            stream.seek(0)
            contains_zip = zipfile.is_zipfile(stream)
            stream.seek(position)
        except PrivacyViolation:
            raise
        except (OSError, ValueError, AttributeError, TypeError, zipfile.BadZipFile) as error:
            raise InspectionError(f'Cannot inspect ZIP signature in archive member {relative}: {error}') from error
        if contains_zip:
            nested_chunks = []
            stream.seek(0)
            remaining = size
            while remaining:
                chunk = stream.read(min(64 * 1024, remaining))
                if not chunk:
                    _fail('Archive member ended before its declared size')
                nested_chunks.append(chunk)
                remaining -= len(chunk)
    if nested_chunks is not None:
        if depth >= MAX_ARCHIVE_DEPTH:
            _fail(f'Nested archive depth limit exceeded in {relative}')
        _inspect_blob(b''.join(nested_chunks), name, f'{relative}!{name}', depth + 1,
                      budget, content_already_charged=True)
    elif collected is not None:
        # Round 6 (SC5-2): a container signature was seen past the embedded
        # scan buffer; the collected tail is audited in full. When the tail
        # exceeds the bounded window the member fails closed instead of
        # silently accepting the uninspected remainder.
        if collect_overflow:
            _fail(f'Embedded container candidate exceeds the safe inspection window in '
                  f'{relative}!{name}')
        if collected_from < len(buffered):
            prefix = bytes(buffered[:collected_from])
            if prefix:
                _scan_embedded_containers(prefix, name, f'{relative}!{name}', depth + 1, budget)
        elif buffered:
            _scan_embedded_containers(bytes(buffered), name, f'{relative}!{name}', depth + 1, budget)
        _scan_embedded_containers(bytes(collected), name, f'{relative}!{name}', depth + 1, budget)
    elif buffered:
        _scan_embedded_containers(bytes(buffered), name, f'{relative}!{name}', depth + 1, budget)


def _consume_tar_member(archive, member, relative, seen, loader_paths, depth, budget):
    if member.issparse():
        _fail('TAR sparse members are not supported')
    name = _safe_member_path(member.name, allow_root_directory=member.isdir())
    _check_private_name(name, f'archive {relative}')

    if member.isfile():
        stream = archive.extractfile(member)
        if stream is None:
            _fail('Archive regular member could not be inspected')
        with stream:
            _consume_regular_member(stream, name, member.size, relative, seen,
                                    loader_paths, depth, budget, already_charged=True)
        return

    if member.isdir():
        if member.size:
            _fail('Archive directory contains unexpected data')
        if name:
            if name in seen:
                _fail('Archive contains duplicate normalized member paths')
            seen.add(name)
        return
    if member.issym():
        if member.size:
            _fail('TAR symbolic link contains unexpected data')
        if name in seen:
            _fail('Archive contains duplicate normalized member paths')
        seen.add(name)
        if len(member.linkname) > MAX_SYMLINK_TARGET_BYTES:
            _fail('Archive link target exceeds the size limit')
        link_bytes = member.linkname.encode('utf-8', 'surrogateescape')
        _check_region_fingerprints(link_bytes, f'archive link target in {relative}', budget)
        _scan_private_text(link_bytes, f'archive link target in {relative}')
        _safe_link_target(name, member.linkname, symbolic=True)
        return
    if member.islnk():
        _fail('Archive hard links are not allowed')
    _fail('Archive contains a device, sparse, or special member')


def _inspect_tar(data, relative, depth, budget, content_already_charged=False):
    if not content_already_charged:
        budget.consume_content(len(data))
    header_count = _preflight_tar(data, relative, budget)
    budget.consume_members(header_count)
    seen = set()
    loader_paths = []
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as archive:
            for member in archive:
                _consume_tar_member(archive, member, relative, seen, loader_paths,
                                    depth, budget)
    except PrivacyViolation:
        raise
    except (OSError, EOFError, RecursionError, tarfile.TarError, ValueError) as error:
        raise InspectionError(f'Cannot safely inspect archive {relative}: {error}') from error
    if _loader_layout_source(loader_paths):
        _fail(f'Private loader source layout found in archive {relative}')
    _sweep_container_bytes(data, relative.rsplit('!', 1)[-1] or relative, relative,
                           depth, budget, covered=[(0, len(data))], scan_whole=False)
    return max(header_count, 1)


def _preflight_zip(data):
    size = len(data)
    tail_size = min(size, 22 + 65_535)
    tail = data[-tail_size:]
    end_offset = None
    end_record = None
    search_at = len(tail)
    while True:
        position = tail.rfind(b'PK\x05\x06', 0, search_at)
        if position < 0:
            break
        if position + 22 <= len(tail):
            candidate = struct.unpack_from('<4s4H2LH', tail, position)
            comment_size = candidate[-1]
            if position + 22 + comment_size == len(tail):
                end_offset = size - tail_size + position
                end_record = candidate
                break
        search_at = position
    if end_record is None:
        _fail('ZIP archive has no valid end record')

    _, disk, directory_disk, disk_entries, total_entries, directory_size, directory_offset, _ = end_record
    if disk or directory_disk or disk_entries != total_entries:
        _fail('Multi-disk ZIP archives are not supported')
    if total_entries == 0xFFFF or directory_size == 0xFFFFFFFF or directory_offset == 0xFFFFFFFF:
        _fail('ZIP64 archives exceed the supported inspection format')
    if total_entries > MAX_ARCHIVE_MEMBERS:
        _fail('Archive exceeds the member-count limit')

    directory_start = end_offset - directory_size
    if directory_start < directory_offset or directory_start < 0:
        _fail('ZIP central directory has an invalid offset')
    directory_end = end_offset
    entries = []
    position = directory_start
    count = 0
    while position < directory_end:
        header = data[position:position + 46]
        if len(header) != 46 or header[:4] != b'PK\x01\x02':
            _fail('ZIP central directory contains an invalid entry')
        fields = struct.unpack('<4s6H3I5H2I', header)
        name_size, extra_size, comment_size = fields[10:13]
        if name_size > 4096:
            _fail('Archive member path exceeds the inspection size limit')
        next_position = position + 46 + name_size + extra_size + comment_size
        if next_position > directory_end:
            _fail('ZIP central directory entry exceeds its declared bounds')
        count += 1
        if count > MAX_ARCHIVE_MEMBERS:
            _fail('Archive exceeds the member-count limit')
        entries.append((position, name_size, extra_size, comment_size))
        position = next_position
    if position != directory_end or count != total_entries:
        _fail('ZIP central directory count or size is inconsistent')
    return directory_start, end_offset, end_offset + 22, size, entries


def _inspect_zip(data, relative, depth, budget):
    seen = set()
    loader_paths = []
    covered = []
    member_count = 0
    try:
        directory_start, directory_end, comment_start, _total, directory_entries = _preflight_zip(data)
        covered.append((directory_start, directory_end))
        covered.append((comment_start - 22, comment_start))
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
            member_count = len(members)
            if len(members) > MAX_ARCHIVE_MEMBERS:
                _fail('Archive exceeds the member-count limit')
            if len(directory_entries) != len(members):
                _fail('ZIP central directory entries do not match the archive members')
            budget.consume_members(len(members))
            first_entry = min((member.header_offset for member in members), default=archive.start_dir)
            if first_entry:
                prefix = data[:first_entry]
                _check_private_digest(hashlib.sha256(prefix).hexdigest(), f'ZIP prefix in {relative}')
                if depth >= MAX_ARCHIVE_DEPTH:
                    _fail(f'Nested archive depth limit exceeded in {relative}')
                try:
                    _inspect_embedded_payload(prefix, relative.rsplit('!', 1)[0].rsplit('/', 1)[-1],
                                              f'{relative}!prefix', depth + 1, budget)
                except InspectionError as error:
                    _fail(f'ZIP archive has a prefix that cannot be safely inspected: {relative} ({error})')
            for index, member in enumerate(members):
                cd_position, cd_name_size, cd_extra_size, cd_comment_size = directory_entries[index]
                cd_start = cd_position + 46
                raw_cd_name = data[cd_start:cd_start + cd_name_size]
                raw_cd_extra = data[cd_start + cd_name_size:cd_start + cd_name_size + cd_extra_size]
                raw_cd_comment = data[cd_start + cd_name_size + cd_extra_size:
                                      cd_start + cd_name_size + cd_extra_size + cd_comment_size]
                _check_signature_digest(raw_cd_name, f'ZIP entry name in {relative}')
                _audit_extra_field(raw_cd_extra, f'ZIP extra field in {relative}', budget)
                _check_region_fingerprints(raw_cd_comment, f'ZIP entry comment in {relative}', budget)
                _scan_private_text(raw_cd_comment, f'ZIP entry comment in {relative}')
                name = _safe_member_path(member.filename, allow_root_directory=member.is_dir())
                _check_private_name(name, f'archive {relative}')
                offset = member.header_offset
                if not 0 <= offset or offset + 30 > len(data):
                    _fail(f'ZIP member local header is out of bounds in {relative}')
                local_name_size = struct.unpack_from('<H', data, offset + 26)[0]
                local_extra_size = struct.unpack_from('<H', data, offset + 28)[0]
                if local_name_size > 4096:
                    _fail(f'ZIP local header path exceeds the inspection size limit in {relative}')
                local_name_end = offset + 30 + local_name_size
                data_start = local_name_end + local_extra_size
                if data_start + member.compress_size > len(data):
                    _fail(f'ZIP member data exceeds the archive bounds in {relative}')
                covered.append((offset, local_name_end))
                _check_signature_digest(data[offset + 30:local_name_end],
                                        f'ZIP local entry name in {relative}')
                _audit_extra_field(data[local_name_end:data_start],
                                   f'ZIP local extra field in {relative}', budget)
                mode = member.external_attr >> 16
                if member.flag_bits & 0x1:
                    _fail('Encrypted archives cannot be safely inspected')
                if stat.S_ISLNK(mode):
                    if member.file_size > MAX_SYMLINK_TARGET_BYTES:
                        _fail('Archive link target exceeds the size limit')
                    with archive.open(member) as stream:
                        target = stream.read(MAX_SYMLINK_TARGET_BYTES + 1)
                    if len(target) > MAX_SYMLINK_TARGET_BYTES:
                        _fail('Archive link target exceeds the size limit')
                    budget.consume_content(len(target))
                    _check_region_fingerprints(target, f'ZIP link target in {relative}', budget)
                    _scan_private_text(target, f'ZIP link target in {relative}')
                    if name:
                        if name in seen:
                            _fail('Archive contains duplicate normalized member paths')
                        seen.add(name)
                    _safe_link_target(name, target.decode('utf-8', errors='strict'), symbolic=True)
                    continue
                if member.is_dir():
                    file_type = stat.S_IFMT(mode)
                    if member.file_size or file_type not in (0, stat.S_IFDIR):
                        _fail('Archive directory contains unexpected data or type')
                    if name:
                        if name in seen:
                            _fail('Archive contains duplicate normalized member paths')
                        seen.add(name)
                    continue
                file_type = stat.S_IFMT(mode)
                if file_type not in (0, stat.S_IFREG):
                    _fail('Archive contains a special member')
                _verify_zip_member_consumption(data, data_start, member.compress_size,
                                               member.compress_type, member.file_size, relative)
                if member.compress_size:
                    covered.append((data_start, data_start + member.compress_size))
                with archive.open(member) as stream:
                    _consume_regular_member(stream, name, member.file_size, relative,
                                            seen, loader_paths, depth, budget,
                                            already_charged=False)
    except PrivacyViolation:
        raise
    except (OSError, EOFError, RuntimeError, RecursionError, NotImplementedError,
            struct.error, zlib.error, zipfile.BadZipFile, zipfile.LargeZipFile,
            ValueError) as error:
        raise InspectionError(f'Cannot safely inspect archive {relative}: {error}') from error
    if _loader_layout_source(loader_paths):
        _fail(f'Private loader source layout found in archive {relative}')
    _sweep_container_bytes(data, relative.rsplit('!', 1)[-1] or relative, relative,
                           depth, budget, covered=covered, scan_whole=False)
    return max(member_count, 1)


def _new_decompressor(kind):
    if kind == 'gzip':
        return zlib.decompressobj(16 + zlib.MAX_WBITS)
    if kind == 'bzip2':
        return bz2.BZ2Decompressor()
    if kind == 'lzma':
        return lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
    return lzma.LZMADecompressor()


def _bounded_decompress(data, kind, relative, budget, best_effort=False):
    """Decompress a bounded stream.

    Returns ``(payload, complete, tail_start)`` where ``tail_start`` is the
    offset of the first byte after the last complete member when the stream
    ends with unconsumed non-padding data (``None`` when complete). In strict
    mode (the default) a stream that fails after producing content raises
    ``UnsafeStream``; with ``best_effort`` the payload recovered so far is
    returned so it can still be inspected.
    """
    chunks = []
    decompressor = _new_decompressor(kind)
    members = 0
    position = 0
    pending = b''
    complete = False
    member_start = 0
    while True:
        if not pending and position < len(data):
            pending = data[position:position + 64 * 1024]
            position += len(pending)
        try:
            output = decompressor.decompress(pending, MAX_DECOMPRESS_CHUNK)
        except PrivacyViolation:
            raise
        except (zlib.error, lzma.LZMAError, OSError, EOFError, ValueError) as error:
            if best_effort:
                break
            message = f'Cannot safely decompress public resource {relative}: {error}'
            if members or chunks:
                raise UnsafeStream(message) from error
            raise InspectionError(message) from error
        pending = getattr(decompressor, 'unconsumed_tail', b'')
        if output:
            budget.consume_content(len(output))
            chunks.append(output)
        if getattr(decompressor, 'eof', False):
            members += 1
            if members > MAX_COMPRESSED_MEMBERS:
                _fail(f'Compressed resource contains too many concatenated members: {relative}')
            pending = getattr(decompressor, 'unused_data', b'').lstrip(b'\x00')
            if pending:
                member_start = position - len(pending)
                decompressor = _new_decompressor(kind)
                continue
            while position < len(data):
                chunk = data[position:position + 64 * 1024]
                position += len(chunk)
                pending = chunk.lstrip(b'\x00')
                if pending:
                    member_start = position - len(pending)
                    decompressor = _new_decompressor(kind)
                    break
            if pending:
                continue
            complete = True
            break
        if not pending and position >= len(data):
            break
    if not complete and not best_effort:
        _fail(f'Compressed resource ended before its end marker: {relative}')
    return b''.join(chunks), complete, (None if complete else member_start)


def _probe_decompression(data, kind):
    try:
        decompressor = _new_decompressor(kind)
        decompressor.decompress(data[:MAX_EMBEDDED_PROBE_BYTES], MAX_DECOMPRESS_CHUNK)
        return True
    except PrivacyViolation:
        raise
    except (zlib.error, lzma.LZMAError, OSError, EOFError, ValueError):
        return False


def _lzma_alone_header(window):
    if len(window) < 13:
        return False
    if window[0] >= 225:
        return False
    return int.from_bytes(window[1:5], 'little') in LZMA_ALONE_DICTIONARY_SIZES


def _lzma_alone_stream(window):
    """Return True when the window starts with a complete LZMA-alone stream."""
    decompressor = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
    produced = 0
    try:
        output = decompressor.decompress(window, MAX_DECOMPRESS_CHUNK)
        produced += len(output)
        while not decompressor.eof and not decompressor.needs_input:
            output = decompressor.decompress(b'', MAX_DECOMPRESS_CHUNK)
            produced += len(output)
            if produced > MAX_ARCHIVE_MEMBER_BYTES:
                return False
    except (lzma.LZMAError, EOFError, ValueError):
        return False
    return decompressor.eof


def _reference_hint(lowered):
    """Cheap necessary condition for the tolerant reference regex to match."""
    hint = lowered.translate(_BYTE_LEET_TABLE, _HINT_SEPARATOR_DELETE)
    return (b'loadersource' in hint or b'loadersrc' in hint
            or b'loaderinclude' in hint)


def _scan_text_window(window, description):
    # Every reference spelling that uses ASCII starts with 'l'/'L'/'1' (loader
    # word), so the cheap gate skips the expensive passes for most binary
    # windows; the fold pass below only runs when a confusable spelling could
    # actually live in the window (runs between letters are covered directly by
    # the separator-tolerant expressions).
    if b'l' in window or b'L' in window or b'1' in window:
        lowered = window.lower()
        for pattern in PRIVATE_TEXT_PATTERNS:
            if pattern in lowered:
                _fail(f'Private loader source path or archive name found in {description}')
        if _reference_hint(lowered) and PRIVATE_REFERENCE_BYTES.search(window):
            _fail(f'Private loader source path or archive name found in {description}')
    if any(marker in window for marker in _CONFUSABLE_MARKERS):
        # Round 6: confusable spellings ('lоader', 'ｌｏａｄｅｒ') are matched by
        # the tolerant expression on bounded slices around each marker, so the
        # pass stays cheap.
        for slice_ in _confusable_slices(window):
            if PRIVATE_REFERENCE_BYTES.search(slice_):
                _fail(f'Private loader source path or archive name found in {description}')
    if not (b'l\x00o\x00' in window or b'\x00l\x00o' in window
            or b'1\x00o\x00' in window or b'\x001\x00o' in window):
        return
    # UTF-16LE/BE references interleave NUL bytes; strip them and rescan.
    compact = window.replace(b'\x00', b'')
    compact_lower = compact.lower()
    if not _reference_hint(compact_lower):
        return
    for pattern in PRIVATE_TEXT_PATTERNS:
        if pattern in compact_lower:
            _fail(f'Private loader source path or archive name found in {description}')
    if PRIVATE_REFERENCE_BYTES.search(compact):
        _fail(f'Private loader source path or archive name found in {description}')


def _scan_private_text(data, description):
    """Scan a byte string for private-loader references, chunked with overlap."""
    if not data:
        return
    position = 0
    length = len(data)
    while position < length:
        window = data[position:position + MAX_TEXT_SCAN_BYTES]
        _scan_text_window(window, description)
        if len(window) < MAX_TEXT_SCAN_BYTES:
            break
        position += len(window) - _TEXT_SCAN_OVERLAP


def _scan_streaming_text(path, relative):
    """Text-scan a plain file of any size without loading it entirely."""
    tail = b''
    try:
        with path.open('rb') as stream:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                window = tail + chunk
                _scan_private_text(window, f'public file {relative}')
                tail = window[-_TEXT_SCAN_OVERLAP:]
    except PrivacyViolation:
        raise
    except OSError as error:
        raise PrivacyViolation(f'Cannot read public file {relative}: {error}') from error


def _uncovered_regions(length, covered):
    regions = []
    cursor = 0
    for start, end in sorted(covered):
        start = max(0, min(start, length))
        end = max(0, min(end, length))
        if end <= cursor:
            continue
        if start > cursor:
            regions.append((cursor, start))
        cursor = end
    if cursor < length:
        regions.append((cursor, length))
    if len(regions) > MAX_UNINSPECTED_REGIONS:
        _fail('Container has more uninspected regions than can be audited safely')
    return regions


def _sweep_container_bytes(data, name, relative, depth, budget, covered=None, scan_whole=True):
    """Audit a container's own bytes: digests, private text and embedded containers."""
    _check_private_digest(hashlib.sha256(data).hexdigest(), f'container in {relative}')
    # Container-level text scan stays bounded; member content is text-scanned
    # while it streams (_consume_regular_member), so references beyond this
    # window are still covered.
    _scan_private_text(data[:MAX_TEXT_SCAN_BYTES], relative)
    if scan_whole:
        _scan_embedded_containers(data, name, relative, depth, budget)
    if covered is None:
        return
    for start, end in _uncovered_regions(len(data), covered):
        region = data[start:end]
        if not region:
            continue
        if len(region) > MAX_UNINSPECTED_REGION_BYTES:
            _fail(f'Container region cannot be safely inspected in {relative}')
        _check_region_fingerprints(region, f'uninspected region in {relative}', budget)
        _scan_private_text(region, f'uninspected region in {relative}')
        _scan_embedded_containers(region, name, f'{relative}!region@{start}', depth, budget)


def _compressed_header_end(data, kind):
    if kind == 'gzip':
        if len(data) < 10 or data[:3] != b'\x1f\x8b\x08':
            return 0
        flags = data[3]
        position = 10
        if flags & 0x04:
            if position + 2 > len(data):
                return len(data)
            position += 2 + int.from_bytes(data[position:position + 2], 'little')
        if flags & 0x08:
            marker = data.find(b'\x00', position)
            position = len(data) if marker < 0 else marker + 1
        if flags & 0x10:
            marker = data.find(b'\x00', position)
            position = len(data) if marker < 0 else marker + 1
        if flags & 0x02:
            position += 2
        return min(position, len(data))
    if kind == 'bzip2':
        return min(len(data), 4)
    if kind == 'xz':
        return min(len(data), 12)
    return min(len(data), 13)


def _sweep_compressed_bytes(data, kind, relative, depth, budget):
    """Audit the raw bytes of a compressed stream: whole digest, header fields and text."""
    _check_private_digest(hashlib.sha256(data).hexdigest(), f'compressed resource in {relative}')
    _scan_private_text(data[:MAX_TEXT_SCAN_BYTES], relative)
    if kind == 'gzip':
        for start, end in _gzip_member_header_ranges(data):
            header = data[start:end]
            if not header:
                continue
            _check_private_digest(hashlib.sha256(header).hexdigest(),
                                  f'compressed header in {relative}')
            _scan_private_text(header, f'compressed header in {relative}')
            if len(header) >= 10 and header[:3] == b'\x1f\x8b\x08':
                _audit_gzip_header_fields(data, start, end, relative, budget)
            _scan_embedded_containers(header, '', f'{relative}!header@{start}',
                                      depth, budget, skip_start=True)
        return
    end = _compressed_header_end(data, kind)
    if not end:
        return
    header = data[:end]
    _check_private_digest(hashlib.sha256(header).hexdigest(), f'compressed header in {relative}')
    _scan_private_text(header, f'compressed header in {relative}')
    _scan_embedded_containers(header, '', f'{relative}!header', depth, budget, skip_start=True)


def _gzip_header_end(data, start):
    """Return the absolute offset just past the gzip member header at ``start``."""
    if len(data) - start < 10 or data[start:start + 3] != b'\x1f\x8b\x08':
        return 0
    flags = data[start + 3]
    position = start + 10
    if flags & 0x04:
        if position + 2 > len(data):
            return len(data)
        position += 2 + int.from_bytes(data[position:position + 2], 'little')
    if flags & 0x08:
        marker = data.find(b'\x00', position)
        position = len(data) if marker < 0 else marker + 1
    if flags & 0x10:
        marker = data.find(b'\x00', position)
        position = len(data) if marker < 0 else marker + 1
    if flags & 0x02:
        position += 2
    return min(position, len(data))


def _gzip_member_end(data, start):
    """Return the offset just past the gzip member (trailer included) at ``start``."""
    decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
    position = start
    pending = b''
    produced = 0
    while True:
        if not pending:
            if position >= len(data):
                return None
            pending = data[position:position + 64 * 1024]
            position += len(pending)
        try:
            output = decompressor.decompress(pending, MAX_DECOMPRESS_CHUNK)
        except (zlib.error, OSError, EOFError, ValueError):
            return None
        produced += len(output)
        if produced > MAX_ARCHIVE_CONTENT_BYTES:
            return None
        pending = getattr(decompressor, 'unconsumed_tail', b'')
        if getattr(decompressor, 'eof', False):
            return position - len(getattr(decompressor, 'unused_data', b''))
        if not pending and position >= len(data):
            return None


def _gzip_member_header_ranges(data):
    """Locate the header of every gzip member, including members after the first."""
    ranges = []
    position = 0
    members = 0
    while position < len(data):
        while position < len(data) and data[position] == 0:
            position += 1
        if position >= len(data) or data[position:position + 3] != b'\x1f\x8b\x08':
            break
        header_end = _gzip_header_end(data, position)
        if header_end <= position:
            break
        ranges.append((position, header_end))
        members += 1
        if members > MAX_COMPRESSED_MEMBERS:
            _fail('Compressed resource contains too many concatenated members')
        member_end = _gzip_member_end(data, position)
        if member_end is None or member_end <= position:
            break
        position = member_end
    return ranges


def _audit_gzip_header_fields(data, start, end, relative, budget):
    flags = data[start + 3]
    position = start + 10
    if flags & 0x04:
        if position + 2 > end:
            _fail(f'gzip member header is truncated in {relative}')
        length = int.from_bytes(data[position:position + 2], 'little')
        if position + 2 + length > end:
            _fail(f'gzip member header is truncated in {relative}')
        field = data[position + 2:position + 2 + length]
        _audit_extra_field(field, f'gzip extra field in {relative}', budget)
        position += 2 + length
    for flag, description in ((0x08, 'gzip original name'), (0x10, 'gzip comment')):
        if not flags & flag:
            continue
        marker = data.find(b'\x00', position, end)
        if marker < 0:
            marker = end
        field = data[position:marker]
        _audit_signature_bytes(field, f'{description} in {relative}')
        _check_private_name(field.decode('utf-8', 'replace'), description)
        position = marker + 1


def _scan_zip_local_records(data, offset, relative, depth, budget):
    """Recover stored or deflated member payloads from ZIP local headers without an end record."""
    position = offset
    count = 0
    while position + 30 <= len(data) and data[position:position + 4] == b'PK\x03\x04':
        count += 1
        if count > MAX_ARCHIVE_MEMBERS:
            _fail(f'ZIP local headers exceed the member-count limit in {relative}')
        flags = struct.unpack_from('<H', data, position + 6)[0]
        method = struct.unpack_from('<H', data, position + 8)[0]
        compressed = struct.unpack_from('<I', data, position + 18)[0]
        name_len = struct.unpack_from('<H', data, position + 26)[0]
        extra_len = struct.unpack_from('<H', data, position + 28)[0]
        if name_len > 4096:
            _fail(f'ZIP local header path exceeds the inspection size limit in {relative}')
        data_start = position + 30 + name_len + extra_len
        if data_start > len(data):
            _fail(f'ZIP local record is truncated in {relative}')
        # Round 5 (SC4-A): the local header itself (raw name + extra fields,
        # which the normal _inspect_zip path audits) must be audited here too.
        _audit_signature_bytes(data[position + 30:position + 30 + name_len],
                               f'ZIP local entry name in {relative}')
        if extra_len:
            _audit_extra_field(data[position + 30 + name_len:data_start],
                               f'ZIP local extra field in {relative}', budget)
        if flags & 0x08 or not compressed:
            # Data-descriptor member (or an empty declaration): the sizes in the
            # local header cannot be trusted, so recover the payload up to the
            # next structural record instead of skipping it silently.
            record_end = _next_zip_record(data, data_start)
            if record_end is None:
                record_end = len(data)
            payload = data[data_start:record_end]
            _audit_zip_local_payload(payload, method, relative, depth, budget, data_start)
            position = record_end
            continue
        if data_start + compressed > len(data):
            _fail(f'ZIP local record is truncated in {relative}')
        payload = data[data_start:data_start + compressed]
        _audit_zip_local_payload(payload, method, relative, depth, budget, data_start)
        position = data_start + compressed
    if position < len(data):
        remainder = data[position:]
        _check_region_fingerprints(remainder, f'ZIP local record remainder in {relative}', budget,
                                   probe_runs=False)
        _scan_private_text(remainder, f'ZIP local record remainder in {relative}')
        _scan_embedded_containers(remainder, '', f'{relative}!remainder@{position}',
                                  depth, budget)


def _next_zip_record(data, start):
    end = None
    for magic in (b'PK\x03\x04', b'PK\x07\x08', b'PK\x01\x02', b'PK\x05\x06'):
        position = data.find(magic, start)
        if position >= 0 and (end is None or position < end):
            end = position
    return end


def _audit_zip_local_payload(payload, method, relative, depth, budget, data_start):
    _check_region_fingerprints(payload, f'ZIP local record in {relative}', budget,
                               probe_runs=False)
    _scan_private_text(payload, f'ZIP local record in {relative}')
    if method == 0:
        recovered = payload
    elif method == 8:
        try:
            recovered, _complete = _bounded_raw_inflate(payload, budget)
        except InspectionError:
            recovered = b''
    else:
        _fail(f'ZIP local record uses an unsupported compression method in {relative}')
    if recovered:
        _check_private_digest(hashlib.sha256(recovered).hexdigest(),
                              f'ZIP local record in {relative}')
        _check_padded_fingerprint_variants(recovered, f'ZIP local record in {relative}')
        _scan_private_text(recovered, f'ZIP local record in {relative}')
        _scan_embedded_containers(recovered, '', f'{relative}!local@{data_start}',
                                  depth + 1, budget)


def _verify_zip_member_consumption(data, data_start, compress_size, method, file_size, relative):
    """Fail closed unless the declared compressed range is exactly what is read.

    STORED members must declare compress_size == file_size; DEFLATE members
    must consume the whole declared range exactly once and not decode beyond
    the declared uncompressed size (so no byte inside a 'covered' range is
    silently skipped by ZipExtFile).
    """
    if file_size > MAX_ARCHIVE_MEMBER_BYTES:
        _fail('Archive member exceeds the inspection size limit')
    if method == 0:
        if compress_size != file_size:
            _fail(f'ZIP stored member declares a mismatched size in {relative}')
        return
    if method != 8 or not compress_size:
        return
    payload = data[data_start:data_start + compress_size]
    decompressor = zlib.decompressobj(-zlib.MAX_WBITS)
    produced = 0
    pending = payload
    while pending and not getattr(decompressor, 'eof', False):
        try:
            output = decompressor.decompress(pending, MAX_DECOMPRESS_CHUNK)
        except (zlib.error, OSError, EOFError, ValueError) as error:
            _fail(f'ZIP member compressed stream cannot be verified in {relative}: {error}')
        produced += len(output)
        if produced > file_size:
            _fail(f'ZIP member decompresses beyond its declared size in {relative}')
        pending = getattr(decompressor, 'unconsumed_tail', b'')
    if not getattr(decompressor, 'eof', False):
        _fail(f'ZIP member compressed stream is truncated in {relative}')
    if getattr(decompressor, 'unused_data', b''):
        _fail(f'ZIP member declares trailing data beyond its compressed stream in {relative}')


def _bounded_raw_inflate(data, budget):
    decompressor = zlib.decompressobj(-zlib.MAX_WBITS)
    chunks = []
    try:
        for index in range(0, len(data), 64 * 1024):
            output = decompressor.decompress(data[index:index + 64 * 1024], MAX_DECOMPRESS_CHUNK)
            if output:
                budget.consume_content(len(output))
                chunks.append(output)
            if getattr(decompressor, 'eof', False):
                break
    except PrivacyViolation:
        raise
    except (zlib.error, OSError, EOFError, ValueError) as error:
        raise InspectionError(f'Cannot inflate raw deflate stream: {error}') from error
    return b''.join(chunks), getattr(decompressor, 'eof', False)


def _tar_walks_cleanly(data):
    """Accept a TAR candidate only when its headers walk cleanly to an end-of-archive block."""
    position = 0
    headers = 0
    while position + 512 <= len(data):
        header = data[position:position + 512]
        if header == b'\x00' * 512:
            return headers > 0
        if not _looks_like_tar_header(header):
            return False
        try:
            size = _parse_tar_octal(header[124:136], 'size')
        except PrivacyViolation:
            return False
        if size > MAX_ARCHIVE_MEMBER_BYTES:
            return False
        headers += 1
        if headers > MAX_ARCHIVE_MEMBERS:
            return False
        position += 512 + ((size + 511) // 512) * 512
    return False


def _verify_embedded_candidate(data, offset, label, relative, depth, budget):
    window = data[offset:]
    if label == 'zip':
        try:
            _preflight_zip(window)
        except PrivacyViolation:
            _scan_zip_local_records(data, offset, relative, depth, budget)
            return None
        return 'zip'
    if label == 'tar':
        if len(window) < 512 or not _looks_like_tar_header(window[:512]):
            return None
        return 'tar' if _tar_walks_cleanly(window) else None
    if label == 'bzip2':
        if len(window) < 5 or window[3:4] not in b'123456789' or window[4:5] != b'1':
            return None
        return 'bzip2' if _probe_decompression(window, 'bzip2') else None
    if label in COMPRESSED_KINDS:
        return label if _probe_decompression(window, label) else None
    if label == 'zstd':
        if len(window) < 5 or window[4] & 0x18:
            return None
        return 'zstd'
    return label if label in UNINSPECTABLE_CONTAINERS else None


def _embedded_candidates(data):
    candidates = []
    for magic, label in EMBEDDED_SIGNATURES:
        start = 0
        while True:
            offset = data.find(magic, start)
            if offset < 0:
                break
            candidates.append((offset, label))
            if len(candidates) > MAX_EMBEDDED_CANDIDATES:
                return candidates
            start = offset + 1
    start = 1
    while True:
        position = data.find(SKIPPABLE_FRAME_TAIL, start)
        if position < 0:
            break
        if position >= 1 and 0x50 <= data[position - 1] <= 0x5F:
            candidates.append((position - 1, SKIPPABLE_FRAME_KIND))
            if len(candidates) > MAX_EMBEDDED_CANDIDATES:
                return candidates
        start = position + 1
    lzma_hits = 0
    for match in _LZMA_ALONE_HINT.finditer(data):
        offset = match.start()
        if not _lzma_alone_header(data[offset:offset + 13]):
            continue
        lzma_hits += 1
        if lzma_hits > MAX_EMBEDDED_CANDIDATES:
            candidates.append((offset, 'lzma'))
            return candidates
        if _lzma_alone_stream(data[offset:offset + MAX_LZMA_PROBE_BYTES]):
            candidates.append((offset, 'lzma'))
            if len(candidates) > MAX_EMBEDDED_CANDIDATES:
                return candidates
    start = 0
    while True:
        offset = data.find(b'ustar', start)
        if offset < 0:
            break
        if offset >= 257:
            candidates.append((offset - 257, 'tar'))
            if len(candidates) > MAX_EMBEDDED_CANDIDATES:
                return candidates
        start = offset + 1
    for offset in range(0, min(len(data), MAX_TAR_CHECKSUM_OFFSETS)):
        checksum = data[offset + 148:offset + 156]
        candidate = checksum.rstrip(b'\0 ').lstrip(b' ')
        if not candidate or candidate.strip(b'01234567'):
            continue
        if _looks_like_tar_header(data[offset:offset + 512]):
            candidates.append((offset, 'tar'))
            if len(candidates) > MAX_EMBEDDED_CANDIDATES:
                return candidates
    return candidates


def _embedded_stream_hit(window):
    """Earliest relaxed embedded-container start inside a rolling window (round 6).

    Only a necessary signal used while streaming content past the embedded
    scan buffer; the collected tail is verified afterwards by
    ``_scan_embedded_containers`` with the full candidate checks.
    """
    best = None
    match = _EMBEDDED_STREAM_SCAN.search(window)
    if match is not None:
        best = match.start()
    position = window.find(SKIPPABLE_FRAME_TAIL)
    while position >= 0:
        if position >= 1 and 0x50 <= window[position - 1] <= 0x5F:
            start = position - 1
            best = start if best is None or start < best else best
            break
        position = window.find(SKIPPABLE_FRAME_TAIL, position + 1)
    for hint in _LZMA_ALONE_HINT.finditer(window):
        start = hint.start()
        if _lzma_alone_header(window[start:start + 13]):
            best = start if best is None or start < best else best
            break
    position = window.find(b'ustar')
    while position >= 0:
        if position >= 257:
            start = position - 257
            best = start if best is None or start < best else best
            break
        position = window.find(b'ustar', position + 1)
    return best


def _scan_embedded_containers(data, name, relative, depth, budget, skip_start=False):
    candidates = _embedded_candidates(data)
    if len(candidates) > MAX_EMBEDDED_CANDIDATES:
        _fail(f'Too many embedded container candidates in {relative}')
    for offset, label in sorted(candidates):
        if skip_start and offset == 0:
            continue
        kind = _verify_embedded_candidate(data, offset, label, relative, depth, budget)
        if kind is None:
            continue
        sub_blob = data[offset:]
        _check_private_digest(hashlib.sha256(sub_blob).hexdigest(),
                              f'embedded container in {relative}')
        if kind in UNINSPECTABLE_CONTAINERS:
            _fail(f'Embedded {kind} container cannot be safely inspected in {relative}')
        if depth >= MAX_ARCHIVE_DEPTH:
            _fail(f'Nested archive depth limit exceeded in {relative}')
        try:
            recovered = _inspect_embedded_payload(sub_blob, name, f'{relative}!embedded@{offset}',
                                                  depth + 1, budget, kind_hint=kind,
                                                  strict_start=offset <= CONTAINER_START_BYTES)
        except InspectionError as error:
            _fail(f'Embedded container cannot be safely inspected in {relative}: {error}')
        if not recovered:
            _fail(f'Embedded container in {relative} produced no inspectable content')


def _inspect_embedded_payload(data, name, relative, depth, budget, content_already_charged=False,
                              kind_hint=None, strict_start=False):
    kind = kind_hint or _kind_from_header(name, data[:512])
    if kind is None:
        try:
            if zipfile.is_zipfile(io.BytesIO(data)):
                kind = 'zip'
        except (OSError, ValueError) as error:
            raise InspectionError(f'Cannot inspect ZIP signature in {relative}: {error}') from error
    if kind == 'zip':
        return _inspect_zip(data, relative, depth, budget)
    if kind in COMPRESSED_KINDS:
        _sweep_compressed_bytes(data, kind, relative, depth, budget)
        expanded, complete, tail_start = _bounded_decompress(
            data, kind, relative, budget, best_effort=True)
        if strict_start and not complete and len(data) <= MAX_INCOMPLETE_CONTAINER_BYTES:
            _fail(f'Embedded compressed container is truncated or corrupt in {relative}')
        if tail_start is not None:
            # Round 5 (SC4-B): bytes after the last complete member are audited
            # regardless of the candidate's position (zero padding is consumed
            # by _bounded_decompress and yields complete=True).
            tail = data[tail_start:]
            _check_region_fingerprints(tail, f'embedded compressed tail in {relative}', budget,
                                       probe_runs=False)
            _scan_private_text(tail, f'embedded compressed tail in {relative}')
        if depth >= MAX_ARCHIVE_DEPTH:
            _fail(f'Nested archive depth limit exceeded in {relative}')
        if not complete and not expanded:
            return 0
        inner = _inspect_embedded_payload(expanded, _compressed_name_without_suffix(name),
                                          relative, depth + 1, budget,
                                          content_already_charged=True)
        return inner or (1 if complete else 0)
    if kind == 'tar':
        return _inspect_tar(data, relative, depth, budget,
                            content_already_charged=content_already_charged)
    _check_private_digest(hashlib.sha256(data).hexdigest(), f'embedded payload in {relative}')
    _check_padded_fingerprint_variants(data, f'embedded payload in {relative}')
    _sweep_container_bytes(data, name, relative, depth, budget)
    return len(data) or 1


def _compressed_name_without_suffix(name):
    folded = name.casefold()
    for suffix in ('.gz', '.bz2', '.xz', '.lzma'):
        if folded.endswith(suffix):
            return name[:-len(suffix)]
    return name


def _inspect_blob(data, name, relative, depth, budget, content_already_charged=False):
    if depth > MAX_ARCHIVE_DEPTH:
        _fail(f'Nested archive depth limit exceeded in {relative}')
    kind = _kind_from_header(name, data[:512])
    if kind is None:
        try:
            if zipfile.is_zipfile(io.BytesIO(data)):
                kind = 'zip'
        except (OSError, ValueError) as error:
            raise InspectionError(f'Cannot inspect ZIP signature in {relative}: {error}') from error

    if kind == 'zip':
        return _inspect_zip(data, relative, depth, budget)
    if kind in COMPRESSED_KINDS:
        _sweep_compressed_bytes(data, kind, relative, depth, budget)
        expanded, _complete, _tail_start = _bounded_decompress(data, kind, relative, budget)
        inner_name = _compressed_name_without_suffix(name)
        inner_kind = _kind_from_header(inner_name, expanded[:512])
        if inner_kind is None:
            try:
                if zipfile.is_zipfile(io.BytesIO(expanded)):
                    inner_kind = 'zip'
            except (OSError, ValueError) as error:
                raise InspectionError(f'Cannot inspect decompressed ZIP signature in {relative}: {error}') from error
        if inner_kind in COMPRESSED_KINDS or inner_kind in {'zip', 'tar'}:
            nested_depth = depth + 1 if inner_kind in COMPRESSED_KINDS else depth
            if nested_depth > MAX_ARCHIVE_DEPTH:
                _fail(f'Nested archive depth limit exceeded in {relative}')
            return _inspect_blob(expanded, inner_name, relative, nested_depth,
                                 budget, content_already_charged=True)
        if len(expanded) > MAX_ARCHIVE_MEMBER_BYTES:
            _fail('Compressed single-file resource exceeds the inspection size limit')
        _check_private_digest(hashlib.sha256(expanded).hexdigest(), f'decompressed public resource {relative}')
        _check_padded_fingerprint_variants(expanded, f'decompressed public resource {relative}')
        if Path(inner_name).suffix.casefold() not in {'.css', '.js'}:
            _fail(f'Compressed single-file resource is not an allowed CSS/JS asset: {relative}')
        _scan_embedded_containers(expanded, inner_name, relative, depth, budget)
        return 0
    if kind == 'tar':
        return _inspect_tar(data, relative, depth, budget,
                            content_already_charged=content_already_charged)

    recognized_suffix = next((suffix for suffix in ARCHIVE_SUFFIXES
                              if name.casefold().endswith(suffix)), None)
    if recognized_suffix:
        _fail(f'Cannot safely inspect declared archive {relative}')
    _scan_embedded_containers(data, name, relative, depth, budget)
    return 0


def _archive_kind(path, relative):
    try:
        with path.open('rb') as stream:
            header = stream.read(512)
    except OSError as error:
        raise PrivacyViolation(f'Cannot read public file {relative}: {error}') from error
    kind = _kind_from_header(path.name, header)
    if kind:
        return kind
    try:
        if zipfile.is_zipfile(path):
            return 'zip'
    except OSError as error:
        raise PrivacyViolation(f'Cannot inspect archive signature in {relative}: {error}') from error
    return None


def _json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PrivacyViolation('Public metadata contains a duplicate JSON key')
        result[key] = value
    return result


def _folded_ascii(value):
    decomposed = unicodedata.normalize('NFKD', str(value))
    mapped = ''.join(
        _ASCII_CONFUSABLES.get(character.casefold(), character)
        for character in decomposed)
    return ''.join(character for character in mapped if ord(character) < 128).casefold()


def _loader_key(value):
    if not isinstance(value, str):
        return False
    folded = _folded_ascii(value).translate(_DIGIT_HOMOGLYPHS)
    tokens = [token for token in re.split(r'[^a-z0-9]+', folded) if token]
    if 'boot' in tokens and 'loader' in tokens:
        return False
    if 'loader' in tokens:
        return True
    # Split spellings such as 'lo-ader' or 'l.o.a.d.e.r' collapse to 'loader'.
    return ''.join(tokens) == 'loader'


def _private_reference(value):
    if not isinstance(value, str):
        return False
    folded = _folded_ascii(value)
    return bool(PRIVATE_ARCHIVE_REFERENCE.search(folded)
                or PRIVATE_LAYOUT_REFERENCE.search(folded))


def _check_private_name(name, description):
    if PRIVATE_ARCHIVE_NAME.search(_folded_ascii(name)):
        _fail(f'Private loader source archive name found in {description}: {name}')


def _read_bounded_file(path, maximum, relative):
    chunks = []
    total = 0
    try:
        with path.open('rb') as stream:
            while True:
                chunk = stream.read(min(64 * 1024, maximum - total + 1))
                if not chunk:
                    break
                total += len(chunk)
                if total > maximum:
                    _fail(f'Public file exceeds the inspection size limit: {relative}')
                chunks.append(chunk)
    except PrivacyViolation:
        raise
    except OSError as error:
        raise PrivacyViolation(f'Cannot read public file {relative}: {error}') from error
    return b''.join(chunks)


def _check_json_depth(text, relative):
    depth = 0
    in_string = False
    escaped = False
    for character in text:
        if in_string:
            if escaped:
                escaped = False
            elif character == '\\':
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in '[{':
            depth += 1
            if depth > MAX_JSON_DEPTH:
                _fail(f'Public JSON nesting depth exceeds the inspection limit: {relative}')
        elif character in ']}':
            depth = max(0, depth - 1)


def _metadata_field(key):
    folded = _folded_ascii(key).translate(_DIGIT_HOMOGLYPHS)
    return re.sub(r'[^a-z0-9]+', '', folded)


def _check_metadata_node(value, context=()):
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            field = _metadata_field(key_text)
            if field == 'sourceartifacts':
                if isinstance(child, dict) and any(_loader_key(component) for component in child):
                    _fail('Release metadata lists loader source as a public source artifact')
                if isinstance(child, list):
                    for entry in child:
                        if isinstance(entry, dict) and any(_loader_key(component) for component in entry):
                            _fail('Release metadata lists loader source as a public source artifact')
                        if _private_reference(entry):
                            _fail('Public JSON references a private loader source archive')
            if field == 'provenance' and isinstance(child, dict):
                for component, metadata in child.items():
                    if _loader_key(component) and isinstance(metadata, dict):
                        fields = {_metadata_field(name) for name in metadata}
                        if fields & {'sourceartifact', 'sourcesha256', 'sourcearchive', 'sourcesize'}:
                            _fail('Catalog provenance exposes loader source metadata')
            if field in {'sourceartifact', 'sourcesha256', 'sourcearchive'} and any(
                    _loader_key(parent) for parent in context):
                _fail('Loader source metadata is forbidden in public JSON')
            if _private_reference(child):
                _fail('Public JSON references a private loader source archive')
            _check_metadata_node(child, context + (key_text,))
    elif isinstance(value, list):
        for child in value:
            _check_metadata_node(child, context)


def _inspect_json(path, relative):
    try:
        raw = _read_bounded_file(path, MAX_JSON_BYTES, relative)
        text = raw.decode('utf-8')
        _check_json_depth(text, relative)
        data = json.loads(text, object_pairs_hook=_json_pairs)
    except PrivacyViolation:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise PrivacyViolation(f'Cannot safely inspect JSON {relative}: {error}') from error
    _check_metadata_node(data)


def _scan_tree_files(root):
    files = []

    def on_walk_error(error):
        raise PrivacyViolation(f'Cannot traverse public tree: {error}') from error

    for current, directories, filenames in os.walk(root, topdown=True, followlinks=False,
                                                   onerror=on_walk_error):
        current_path = Path(current)
        directories.sort()
        filenames.sort()
        for name in list(directories):
            item = current_path / name
            relative = item.relative_to(root).as_posix()
            _check_private_name(name, f'public directory {relative}')
            try:
                mode = item.lstat().st_mode
            except OSError as error:
                raise PrivacyViolation(f'Cannot inspect public directory {relative}: {error}') from error
            if stat.S_ISLNK(mode):
                _fail(f'Public tree contains a symlink directory: {relative}')
            if not stat.S_ISDIR(mode):
                _fail(f'Public tree contains a non-directory entry: {relative}')
        for name in filenames:
            item = current_path / name
            relative = item.relative_to(root).as_posix()
            try:
                mode = item.lstat().st_mode
            except OSError as error:
                raise PrivacyViolation(f'Cannot inspect public file {relative}: {error}') from error
            if stat.S_ISLNK(mode):
                _fail(f'Public tree contains a symlink file: {relative}')
            if not stat.S_ISREG(mode):
                _fail(f'Public tree contains a special file: {relative}')
            files.append((item, relative))
    return files


def _public_file_stat(path, relative):
    try:
        info = path.stat()
    except OSError as error:
        raise PrivacyViolation(f'Cannot stat public file {relative}: {error}') from error
    if not stat.S_ISREG(info.st_mode):
        _fail(f'Public tree contains a special file: {relative}')
    return info


def validate_site(site_root):
    root = Path(site_root)
    try:
        root_mode = root.lstat().st_mode
    except OSError as error:
        raise PrivacyViolation(f'Cannot inspect public site root {root}: {error}') from error
    if stat.S_ISLNK(root_mode) or not stat.S_ISDIR(root_mode):
        _fail(f'Public site root is missing or is a symlink: {root}')
    try:
        root = root.resolve(strict=True)
    except OSError as error:
        raise PrivacyViolation(f'Cannot resolve public site root {root}: {error}') from error
    files = _scan_tree_files(root)
    archive_count = 0
    fingerprint_scan_bytes = 0

    for path, relative in files:
        _check_private_name(path.name, f'public tree {relative}')
        kind = _archive_kind(path, relative)
        info = _public_file_stat(path, relative)
        if kind:
            if info.st_size > MAX_ARCHIVE_BYTES:
                _fail(f'Archive exceeds the compressed-size limit: {relative}')
            data = _read_bounded_file(path, MAX_ARCHIVE_BYTES, relative)
            _inspect_blob(data, path.name, relative, 0, _InspectionBudget())
            archive_count += 1

        native_source = _is_native_source(path.name)
        parts = relative.replace('\\', '/').casefold().split('/')
        if native_source and 'loader' in parts[:-1]:
            _fail(f'Raw loader source path found in public tree: {relative}')
        if native_source and info.st_size > MAX_RAW_SOURCE_BYTES:
            _fail(f'Raw native source exceeds the inspection size limit: {relative}')
        if info.st_size <= MAX_FINGERPRINT_FILE_BYTES or native_source:
            maximum = MAX_RAW_SOURCE_BYTES if native_source else MAX_FINGERPRINT_FILE_BYTES
            fingerprint_scan_bytes += info.st_size
            if fingerprint_scan_bytes > MAX_SITE_FINGERPRINT_BYTES:
                _fail('Public site exceeds the cumulative raw fingerprint scan limit')
            try:
                with path.open('rb') as stream:
                    digest, _ = _sha256_stream(stream, maximum)
            except OSError as error:
                raise PrivacyViolation(f'Cannot read public file {relative}: {error}') from error
            _check_private_digest(digest, f'public file {relative}')

        if kind is None:
            if info.st_size <= MAX_TEXT_SCAN_BYTES:
                plain = _read_bounded_file(path, MAX_TEXT_SCAN_BYTES, relative)
                _scan_private_text(plain, f'public file {relative}')
                # Round 6 (SC5-1): plain files also carry the padded-copy class.
                _check_padded_fingerprint_variants(plain, f'public file {relative}')
                if not native_source and info.st_size <= MAX_EMBEDDED_SCAN_BYTES:
                    _scan_embedded_containers(plain, path.name, relative, 0, _InspectionBudget())
            else:
                _scan_streaming_text(path, relative)

        if path.suffix.casefold() == '.json':
            _inspect_json(path, relative)

    return {'files': len(files), 'archives': archive_count}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('site_roots', nargs='+', type=Path, help='public/ or a built dist/ site root')
    arguments = parser.parse_args(argv)
    try:
        for root in arguments.site_roots:
            result = validate_site(root)
            print(f'SOURCE PRIVACY VALIDATION PASSED: {root} ({result["files"]} files, {result["archives"]} archives inspected)')
    except PrivacyViolation as error:
        print('DO NOT DEPLOY — source privacy validation failed:', error)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
