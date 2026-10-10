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

// The Heltec V4 DualBoot uses the same guard with its own layout: the update is
// refused unless the installed 0x8000 table matches the v1 layout, and the
// applications go to the meshcore/meshtastic slots.
const v4Device = catalog.devices.find(x => x.id === 'heltec-v4');
const v4Plan = (loaderChanged = v4Device.update.loaderChanged) => resolveFlashPlan({
  ...v4Device,
  update: { ...v4Device.update, loaderChanged },
}, 'update', fetchBytes);

function v4Hardware(resolved, changes = {}) {
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

test('Heltec V4 update targets the OTA v1 slots and includes the loader by flag', async () => {
  assert.equal(v4Device.update.requiredLayout.id, 'ape-heltec-v4-dualboot-ota-v1');
  const resolved = await v4Plan(true);
  assert.deepEqual(resolved.parts.map(p => p.name), ['meshcore', 'meshtastic', 'loader']);
  const calls = [];
  await executeFlashPlan(resolved, {
    checkUpdate: p => checkLoaderUpdate(p, v4Hardware(p)),
    onState: state => calls.push(state),
    erase: async () => calls.push('erase-called'),
    write: async () => calls.push(...resolved.parts.map(p => `write-${p.address.toString(16)}`)),
    verify: async () => calls.push('verified'),
  });
  assert.deepEqual(calls, ['write', 'write-1a0000', 'write-3a0000', 'write-20000', 'verify', 'verified']);
});

test('Heltec V4 apps-only update validates without the loader part', async () => {
  const resolved = await v4Plan(false);
  assert.deepEqual(resolved.parts.map(p => p.name), ['meshcore', 'meshtastic']);
  const calls = [];
  await executeFlashPlan(resolved, {
    checkUpdate: p => checkLoaderUpdate(p, v4Hardware(p)),
    onState: () => {}, erase: async () => calls.push('erase'),
    write: async () => calls.push('write'), verify: async () => calls.push('verify'),
  });
  assert.deepEqual(calls, ['write', 'verify']);
});

test('Heltec V4 device on an older layout is refused without erase or write', async () => {
  const resolved = await v4Plan();
  let mutations = 0;
  await assert.rejects(executeFlashPlan(resolved, {
    checkUpdate: p => checkLoaderUpdate(p, v4Hardware(p, { flashMd5sum: async () => '0'.repeat(32) })),
    onState: () => {}, erase: async () => mutations++, write: async () => mutations++, verify: async () => {},
  }), /Clean install/);
  assert.equal(mutations, 0);
});

for (const [scenario, mutate] of [
  ['tampered meshcore', r => { r.parts.find(p => p.name === 'meshcore').data[48] ^= 1; }],
  ['tampered loader', r => { r.parts.find(p => p.name === 'loader').data[48] ^= 1; }],
  ['meshcore at the legacy offset', r => { r.parts.find(p => p.name === 'meshcore').address = 0xa0000; }],
  ['missing meshtastic', r => { r.parts = r.parts.filter(p => p.name !== 'meshtastic'); }],
  ['missing layout guard', r => { r.requiredLayout = null; }],
]) {
  test(`Heltec V4 write boundary rejects ${scenario} without erase/write`, async () => {
    const resolved = await v4Plan(true);
    mutate(resolved);
    let mutations = 0;
    await assert.rejects(executeFlashPlan(resolved, {
      checkUpdate: p => checkLoaderUpdate(p, v4Hardware(p)),
      onState: () => {}, erase: async () => mutations++, write: async () => mutations++, verify: async () => {},
    }));
    assert.equal(mutations, 0);
  });
}

