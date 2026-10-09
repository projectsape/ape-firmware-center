#!/usr/bin/env python3
"""Keep published firmware distribution free of build/source archives."""
import argparse
import json
import re
import unicodedata
from pathlib import Path

ARCHIVE_SUFFIXES = (
    '.tar', '.tar.gz', '.tar.xz', '.tar.bz2', '.tar.zst', '.tgz', '.tbz',
    '.tbz2', '.txz', '.tzst', '.zip', '.7z', '.rar', '.gz', '.bz2', '.xz',
    '.lzma', '.zst', '.lz4',
)


def _metadata(value):
    if isinstance(value, dict):
        for key, child in value.items():
            folded = unicodedata.normalize('NFKD', str(key)).casefold()
            field = re.sub(r'[^a-z0-9]', '', folded)
            if field in {'sourceartifacts', 'sourceartifact', 'sourcesha256', 'sourcearchive', 'sourcesize'}:
                raise ValueError('Build source download metadata is forbidden')
            _metadata(child)
    elif isinstance(value, list):
        for child in value:
            _metadata(child)


def validate(site_root):
    root = Path(site_root)
    for path in root.rglob('*'):
        if path.name.casefold().endswith(ARCHIVE_SUFFIXES):
            raise ValueError(f'Build/source archive is forbidden: {path.relative_to(root)}')
        if path.is_file():
            from validate_source_privacy import _archive_kind, _is_native_source
            if _is_native_source(path):
                raise ValueError(f'Native firmware source is forbidden: {path.relative_to(root)}')
            if _archive_kind(path, path.relative_to(root).as_posix()):
                raise ValueError(f'Renamed build/source archive is forbidden: {path.relative_to(root)}')
            if path.suffix.casefold() == '.json':
                _metadata(json.loads(path.read_text(encoding='utf-8')))
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('site_roots', nargs='+', type=Path)
    arguments = parser.parse_args()
    try:
        for root in arguments.site_roots:
            validate(root)
            print(f'BINARY DISTRIBUTION VALIDATION PASSED: {root}')
    except ValueError as error:
        print('DO NOT DEPLOY — binary distribution policy failed:', error)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
