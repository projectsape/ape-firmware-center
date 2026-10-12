#!/usr/bin/env python3
"""Unit tests for validate_flash_plans.py bounds + overlap + loader rules.

Run: python3 scripts/test_flash_plans.py
"""

import sys
import contextlib
import copy
import io
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_flash_plans as v


class TestBounds(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pub = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _mk(self, name, size):
        p = self.pub / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"\x00" * size)

    def _errors(self, offset, size=0x1000, name="a.bin", fsize=0x10000):
        self._mk(name, size)
        return v.find_bounds_errors("d", "update", [{"name": "a", "file": name, "offset": offset}], fsize, self.pub)

    def test_valid_range(self):
        self.assertEqual(self._errors("0x0"), [])

    def test_end_exceeds_flash(self):
        errs = self._errors("0xF001")  # 0xF001 + 0x1000 > 0x10000
        self.assertTrue(any("exceeds flash" in e for e in errs))

    def test_negative_offset(self):
        self.assertTrue(self._errors(-1))

    def test_empty_file(self):
        self.assertTrue(self._errors("0x0", size=0))

    def test_missing_file(self):
        errs = v.find_bounds_errors("d", "update", [{"name": "m", "file": "missing.bin", "offset": "0x0"}], 0x10000, self.pub)
        self.assertTrue(any("file not found" in e for e in errs))

    def test_invalid_offset(self):
        errs = v.find_bounds_errors("d", "update", [{"name": "x", "file": "a.bin", "offset": "not-a-number"}], 0x10000, self.pub)
        self.assertTrue(any("invalid offset" in e for e in errs))


class TestOverlaps(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pub = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _check(self, ranges):
        # ranges: [(name, file, offset, size), ...]
        parts = []
        for name, file, offset, size in ranges:
            p = self.pub / file
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"\x00" * size)
            parts.append({"name": name, "file": file, "offset": offset})
        return v.find_overlap_errors("d", "update", parts, self.pub)

    def test_adjacent_pass(self):
        self.assertEqual(self._check([("a", "a.bin", "0x0", 0x1000), ("b", "b.bin", "0x1000", 0x1000)]), [])

    def test_separated_pass(self):
        self.assertEqual(self._check([("a", "a.bin", "0x0", 0x1000), ("b", "b.bin", "0x2000", 0x1000)]), [])

    def test_partial_overlap_fail(self):
        self.assertTrue(self._check([("a", "a.bin", "0x0", 0x1000), ("b", "b.bin", "0x800", 0x1000)]))

    def test_contained_fail(self):
        self.assertTrue(self._check([("a", "a.bin", "0x0", 0x1000), ("b", "b.bin", "0x200", 0x100)]))

    def test_same_offset_fail(self):
        self.assertTrue(self._check([("a", "a.bin", "0x0", 0x1000), ("b", "b.bin", "0x0", 0x1000)]))


class TestLoaderInclusion(unittest.TestCase):
    def test_loaderChanged_false_omits_loader(self):
        dev = {
            "loader": {"file": "loader.bin", "offset": "0x20000"},
            "update": {"loaderChanged": False, "parts": [{"name": "app", "file": "app.bin", "offset": "0x10000"}]},
            "factory": {"parts": []},
        }
        plans = v.collect_plan_parts(dev)
        self.assertEqual([p["name"] for p in plans["update"]], ["app"])

    def test_loaderChanged_true_includes_loader(self):
        dev = {
            "loader": {"file": "loader.bin", "offset": "0x20000"},
            "update": {"loaderChanged": True, "parts": [{"name": "app", "file": "app.bin", "offset": "0x10000"}]},
            "factory": {"parts": []},
        }
        plans = v.collect_plan_parts(dev)
        self.assertEqual([p["name"] for p in plans["update"]], ["app", "loader"])


class TestV3Layout(unittest.TestCase):
    def test_valid_v3_guard_and_factory(self):
        catalog = json.loads(v.CATALOG.read_text())
        dev = next(d for d in catalog['devices'] if d['id'] == 'heltec-v3')
        self.assertEqual(v.find_v3_layout_errors(dev, v.PUBLIC), [])

    def test_invalid_v3_metadata_and_slots(self):
        catalog = json.loads(v.CATALOG.read_text())
        original = next(d for d in catalog['devices'] if d['id'] == 'heltec-v3')
        mutations = {
            'wrong capacity': lambda d: d.update(flashSize='16MB'),
            'wrong chip': lambda d: d.update(chipFamily='ESP32-C6'),
            'unverified size': lambda d: d['update'].update(requireVerifiedFlashSize=False),
            'wrong layout': lambda d: d['update']['requiredLayout'].update(id='other'),
            'wrong sector': lambda d: d['update']['requiredLayout'].update(offset='0x9000'),
            'wrong hash': lambda d: d['update']['requiredLayout'].update(sha256='0' * 64),
            'wrong artifact': lambda d: d['update']['requiredLayout'].update(file=d['loader']['file']),
            'missing table': lambda d: d['update']['requiredLayout'].update(file='missing.bin'),
            'escaped table': lambda d: d['update']['requiredLayout'].update(file='../outside.bin'),
            'wrong app offset': lambda d: d['update']['parts'][0].update(offset='0x1a0000'),
            'duplicate app': lambda d: d['update']['parts'].append(d['update']['parts'][0]),
            'missing app': lambda d: d['update']['parts'].pop(),
            'wrong factory': lambda d: d['factory']['parts'][0].update(file=d['loader']['file']),
            'wrong loader offset': lambda d: d['loader'].update(offset='0x10000'),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                device = copy.deepcopy(original)
                mutate(device)
                self.assertTrue(v.find_v3_layout_errors(device, v.PUBLIC))

    def test_v3_missing_layout_guard_blocks_deploy(self):
        catalog = json.loads(v.CATALOG.read_text())
        dev = next(d for d in catalog['devices'] if d['id'] == 'heltec-v3')
        dev['update'].pop('requiredLayout', None)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'catalog.json'
            path.write_text(json.dumps(catalog))
            with patch.object(v, 'CATALOG', path), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(v.main(), 1)


if __name__ == "__main__":
    unittest.main()
