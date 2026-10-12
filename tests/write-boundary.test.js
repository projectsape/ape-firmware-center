import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { readFile, mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { build } from 'esbuild';
import { resolveFlashPlan } from '../src/catalog.js';
import { md5Hex } from '../src/md5.js';

// esptool-js has extensionless browser imports. Bundle exactly as Vite does,
// so these tests exercise the real Flasher rather than a copy.
const directory = await mkdtemp(join(tmpdir(), 'ape-flasher-test-'));
after(() => rm(directory, { recursive: true, force: true }));
const outfile = join(directory, 'flasher.mjs');
await build({ entryPoints: [new URL('../src/flasher.js', import.meta.url).pathname],
  bundle: true, outfile, platform: 'node', format: 'esm' });
const { Flasher } = await import(pathToFileURL(outfile));
const catalog = JSON.parse(await readFile(new URL('../public/data/firmware-catalog.json', import.meta.url)));
const fetchBytes = async file => new Uint8Array(await readFile(new URL('../public/' + file, import.meta.url)));

for (const device of catalog.devices) {
  for (const mode of ['update', 'wipe']) {
    test(`${device.id}/${mode}: matching hardware preserves write/erase/MD5 order`, async () => {
      const plan = await resolveFlashPlan(device, mode, fetchBytes);
      const flasher = new Flasher();
      const calls = [];
      flasher.loader = {
        chip: { CHIP_NAME: 'ESP32-S3' },
        CHIP_DETECT_MAGIC_REG_ADDR: 0x40001000,
        readReg: async () => { calls.push('live-chip'); return 0x09; },
        DETECTED_FLASH_SIZES: { 0x17: '8MB', 0x18: '16MB' },
        readFlashId: async () => { calls.push('live-size'); return (device.flashSize === '8MB' ? 0x17 : 0x18) << 16; },
        eraseFlash: async () => calls.push('erase'),
        writeFlash: async options => {
          calls.push('write');
          assert.equal(options.eraseAll, false); // explicit erase only, never twice
          assert.deepEqual(options.fileArray.map(p => p.address), plan.parts.map(p => p.address));
        },
        flashMd5sum: async (address, size) => {
          const layout = address === 0x8000;
          calls.push(layout ? 'layout' : 'verify');
          const bytes = layout ? plan.requiredLayout.data : plan.parts.find(p => p.address === address).data;
          assert.equal(bytes.length, size);
          return md5Hex(bytes);
        },
      };
      await flasher.flashPlan(plan);
      assert.deepEqual(calls.slice(0, 2), ['live-chip', 'live-size']);
      assert.equal(calls.filter(x => x === 'erase').length, mode === 'wipe' ? 1 : 0);
      if (mode === 'wipe') assert.ok(calls.indexOf('erase') < calls.indexOf('write'));
      if (plan.requiredLayout) assert.ok(calls.indexOf('layout') < calls.indexOf('write'));
      assert.equal(calls.filter(x => x === 'verify').length, plan.parts.length);
      assert.ok(calls.indexOf('write') < calls.indexOf('verify'));
    });
    for (const scenario of ['changed-chip', 'disconnected']) {
      test(`${device.id}/${mode}: ${scenario} is not hidden by cached CHIP_NAME`, async () => {
        const plan = await resolveFlashPlan(device, mode, fetchBytes);
        const flasher = new Flasher();
        let mutations = 0;
        flasher.loader = {
          chip: { CHIP_NAME: 'ESP32-S3' },
          CHIP_DETECT_MAGIC_REG_ADDR: 0x40001000,
          readReg: async address => {
            assert.equal(address, 0x40001000);
            if (scenario === 'disconnected') throw Error('port disconnected');
            return 0x2ce0806f; // ESP32-C6; cached CHIP_NAME still says S3.
          },
          DETECTED_FLASH_SIZES: { 0x17: '8MB', 0x18: '16MB' },
          readFlashId: async () => (device.flashSize === '8MB' ? 0x17 : 0x18) << 16,
          eraseFlash: async () => mutations++, writeFlash: async () => mutations++,
          flashMd5sum: async (address, size) => {
            const bytes = address === 0x8000 ? plan.requiredLayout?.data
              : plan.parts.find(p => p.address === address)?.data;
            assert.equal(bytes.length, size);
            return md5Hex(bytes);
          },
        };
        await assert.rejects(flasher.flashPlan(plan), e => e.code === (
          scenario === 'disconnected' ? 'not_connected' : 'wrong_chip'));
        assert.equal(mutations, 0);
      });
    }
    test(`${device.id}/${mode}: changed flash size is refused at the write boundary`, async () => {
      const plan = await resolveFlashPlan(device, mode, fetchBytes);
      const flasher = new Flasher();
      let mutations = 0;
      flasher.loader = {
        chip: { CHIP_NAME: 'ESP32-S3' },
        CHIP_DETECT_MAGIC_REG_ADDR: 0x40001000,
        readReg: async () => 0x09,
        DETECTED_FLASH_SIZES: { 0x17: '8MB', 0x18: '16MB' },
        readFlashId: async () => (device.flashSize === '8MB' ? 0x18 : 0x17) << 16,
        eraseFlash: async () => mutations++,
        writeFlash: async () => mutations++,
        flashMd5sum: async () => '',
      };
      await assert.rejects(flasher.flashPlan(plan), e => e.code === 'wrong_flash_size');
      assert.equal(mutations, 0);
    });
  }
}
