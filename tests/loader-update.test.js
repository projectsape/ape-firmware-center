import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { checkLoaderUpdate, executeFlashPlan } from '../src/loader-update.js';
import { getHardwareCards, resolveFlashPlan } from '../src/catalog.js';
import { prepareFlashSession } from '../src/flash-flow.js';
import { md5Hex } from '../src/md5.js';

const catalog = JSON.parse(await readFile(new URL('../public/data/firmware-catalog.json', import.meta.url)));
const device = catalog.devices.find(x => x.id === 't147-lora-dualboot');
const fetchBytes = async file => new Uint8Array(await readFile(new URL('../public/' + file, import.meta.url)));
const plan = (loaderChanged = device.update.loaderChanged) => resolveFlashPlan({
  ...device,
  update: { ...device.update, loaderChanged },
}, 'update', fetchBytes);

function hardware(resolved, changes = {}) {
  return {
    chipName: 'ESP32-S3',
    checkChipFamily: (expected, actual) => assert.equal(expected, actual),
    checkFlashSize: async () => ({ reliable: true, detectedFlashSize: '16MB' }),
    flashMd5sum: async (address, size) => {
      assert.equal(address, 0x8000);
      assert.equal(size, 4096);
      return md5Hex(resolved.requiredLayout.data);
    },
    ...changes,
  };
}

test('T147 has exactly DualBoot LoRa + unchanged NoLoRa; standalone is local-only', () => {
  const cards = getHardwareCards(catalog);
  assert.deepEqual(cards.find(x => x.id === 't147').devices.map(x => x.id), ['t147-lora-dualboot', 't147-nolora']);
  assert.equal((catalog.archivedDevices || []).some(x => x.id === 't147-lora'), false);
  assert.deepEqual(device.update.parts.map(x => x.name), ['wadamesh', 'meshtastic']);
  assert.equal(typeof device.update.loaderChanged, 'boolean');
});

test('published UPDATE retains both apps and includes the loader only by flag', async () => {
  const resolved = await plan();
  assert.deepEqual(resolved.parts.map(p => p.name), device.update.loaderChanged
    ? ['wadamesh', 'meshtastic', 'loader'] : ['wadamesh', 'meshtastic']);
  assert.equal(resolved.eraseAll, false);
});

test('matching layout permits app + loader writes, without erase', async () => {
  const resolved = await plan(true);
  assert.deepEqual(resolved.parts.map(p => p.name), ['wadamesh', 'meshtastic', 'loader']);
  const calls = [];
  await executeFlashPlan(resolved, {
    checkUpdate: p => checkLoaderUpdate(p, hardware(p)),
    onState: state => calls.push(state),
    erase: async () => calls.push('erase-called'),
    write: async () => calls.push(...resolved.parts.map(p => `write-${p.address.toString(16)}`)),
    verify: async () => calls.push('verified'),
  });
  assert.deepEqual(calls, ['write', 'write-1a0000', 'write-520000', 'write-20000', 'verify', 'verified']);
});

test('apps-only update (loader unchanged) validates without the loader part', async () => {
  const resolved = await plan(false);
  assert.deepEqual(resolved.parts.map(p => p.name), ['wadamesh', 'meshtastic']);
  const calls = [];
  await executeFlashPlan(resolved, {
    checkUpdate: p => checkLoaderUpdate(p, hardware(p)),
    onState: () => {},
    erase: async () => calls.push('erase'),
    write: async () => calls.push('write'),
    verify: async () => calls.push('verify'),
  });
  assert.deepEqual(calls, ['write', 'verify']);
});

for (const scenario of ['wrong-table', 'unreadable-table', 'unknown-size', 'wrong-size', 'wrong-chip',
  'tampered-app', 'tampered-loader', 'tampered-table', 'wrong-app-offset', 'wrong-loader-offset',
  'missing-app', 'unknown-part', 'missing-guard']) {
  test(`write boundary rejects ${scenario} without erase/write, even without preparation`, async () => {
    const resolved = await plan(scenario === 'tampered-loader' || scenario === 'wrong-loader-offset'
      ? true : device.update.loaderChanged);
    let changes = {};
    if (scenario === 'wrong-table') changes.flashMd5sum = async () => '0'.repeat(32);
    if (scenario === 'unreadable-table') changes.flashMd5sum = async () => { throw new Error('read failed'); };
    if (scenario === 'unknown-size') changes.checkFlashSize = async () => ({ reliable: false, detectedFlashSize: null });
    if (scenario === 'wrong-size') changes.checkFlashSize = async () => ({ reliable: true, detectedFlashSize: '8MB' });
    if (scenario === 'wrong-chip') changes.chipName = 'ESP32-C6';
    if (scenario === 'tampered-app') resolved.parts.find(p => p.name === 'wadamesh').data[48] ^= 1;
    if (scenario === 'tampered-loader') resolved.parts.find(p => p.name === 'loader').data[48] ^= 1;
    if (scenario === 'tampered-table') resolved.requiredLayout.data[48] ^= 1;
    if (scenario === 'wrong-app-offset') resolved.parts.find(p => p.name === 'wadamesh').address = 0x10000;
    if (scenario === 'wrong-loader-offset') resolved.parts.find(p => p.name === 'loader').address = 0x10000;
    if (scenario === 'missing-app') resolved.parts = resolved.parts.filter(p => p.name !== 'meshtastic');
    if (scenario === 'unknown-part') resolved.parts.push({ name: 'extra', file: 'extra.bin', address: 0x900000, sha256: '0'.repeat(64), data: new Uint8Array([1]) });
    if (scenario === 'missing-guard') resolved.requiredLayout = null;
    let mutations = 0;
    await assert.rejects(executeFlashPlan(resolved, {
      checkUpdate: p => checkLoaderUpdate(p, hardware(p, changes)),
      onState: () => {}, erase: async () => mutations++, write: async () => mutations++, verify: async () => {},
    }));
    assert.equal(mutations, 0);
  });
}

test('preparation checks layout after port selection/download/chip/flash', async () => {
  const resolved = await plan();
  const calls = [];
  const flasher = {
    selectPort: async () => calls.push('port'),
    connect: async () => { calls.push('connect'); return { chipName: 'ESP32-S3' }; },
    checkChipFamily: () => calls.push('chip'),
    checkFlashSize: async () => calls.push('size'),
    checkUpdatePlan: async p => { calls.push('layout'); await checkLoaderUpdate(p, hardware(p)); },
  };
  await prepareFlashSession({ flasher, device, mode: 'update', resolvePlan: async () => { calls.push('download'); return resolved; } });
  assert.deepEqual(calls, ['port', 'download', 'connect', 'chip', 'size', 'layout']);
});

test('layout artifact is SHA-verified before connection', async () => {
  await assert.rejects(resolveFlashPlan(device, 'update', async file => {
    const bytes = await fetchBytes(file);
    if (file.includes('partitions-ota-v2')) bytes[0] ^= 1;
    return bytes;
  }), /SHA-256 mismatch/);
});
