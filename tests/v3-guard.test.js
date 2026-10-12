import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolveFlashPlan } from '../src/catalog.js';
import { checkLoaderUpdate, executeFlashPlan } from '../src/loader-update.js';
import { prepareFlashSession } from '../src/flash-flow.js';
import { md5Hex } from '../src/md5.js';

const catalog = JSON.parse(await readFile(new URL('../public/data/firmware-catalog.json', import.meta.url)));
const device = catalog.devices.find(d => d.id === 'heltec-v3');
const fetchBytes = async file => new Uint8Array(await readFile(new URL('../public/' + file, import.meta.url)));
const plan = (loaderChanged = false) => resolveFlashPlan({
  ...device, update: { ...device.update, loaderChanged },
}, 'update', fetchBytes);
const hardware = (resolved, changes = {}) => ({
  chipName: 'ESP32-S3',
  checkChipFamily: (expected, actual) => assert.equal(expected, actual),
  checkFlashSize: async expected => {
    assert.equal(expected, '8MB');
    return { reliable: true, detectedFlashSize: '8MB' };
  },
  flashMd5sum: async (address, size) => {
    assert.equal(address, 0x8000);
    assert.equal(size, 4096);
    return md5Hex(resolved.requiredLayout.data);
  },
  ...changes,
});

test('V3 with a different installed table cannot erase or write', async () => {
  const resolved = await plan();
  assert.equal(resolved.requiredLayout.size, 4096);
  assert.equal(resolved.requiredLayout.address, 0x8000);
  let mutations = 0;
  await assert.rejects(executeFlashPlan(resolved, {
    checkUpdate: p => checkLoaderUpdate(p, hardware(p, { flashMd5sum: async () => '0'.repeat(32) })),
    onState: () => {}, erase: async () => mutations++, write: async () => mutations++, verify: async () => {},
  }), /layout|partition/i);
  assert.equal(mutations, 0);
});

for (const loaderChanged of [false, true]) {
  test(`V3 accepts its factory table with loaderChanged=${loaderChanged}`, async () => {
    const resolved = await plan(loaderChanged);
    const factory = await fetchBytes(device.factory.parts[0].file);
    assert.deepEqual(resolved.requiredLayout.data, factory.slice(0x8000, 0x9000));
    assert.equal(resolved.requiredLayout.id, 'ape-heltec-v3-dualboot-8mb-v1');
    assert.deepEqual(resolved.parts.map(p => p.address), loaderChanged
      ? [0xa0000, 0x300000, 0x20000] : [0xa0000, 0x300000]);
    await checkLoaderUpdate(resolved, hardware(resolved));
  });
}

for (const scenario of ['unknown-size', 'wrong-size', 'wrong-chip', 'unreadable-table',
  'tampered-app', 'tampered-loader', 'tampered-table', 'wrong-app-offset', 'oversize-app',
  'missing-app', 'duplicate-app', 'unknown-part', 'missing-guard']) {
  test(`V3 rejects ${scenario} before any mutation`, async () => {
    const resolved = await plan(true);
    const changes = {};
    if (scenario === 'unknown-size') changes.checkFlashSize = async () => ({ reliable: false });
    if (scenario === 'wrong-size') changes.checkFlashSize = async () => ({ reliable: true, detectedFlashSize: '16MB' });
    if (scenario === 'wrong-chip') changes.chipName = 'ESP32-C6';
    if (scenario === 'unreadable-table') changes.flashMd5sum = async () => { throw Error('disconnected'); };
    if (scenario === 'tampered-app') resolved.parts[0].data[48] ^= 1;
    if (scenario === 'tampered-loader') resolved.parts[2].data[48] ^= 1;
    if (scenario === 'tampered-table') resolved.requiredLayout.data[48] ^= 1;
    if (scenario === 'wrong-app-offset') resolved.parts[0].address = 0x1a0000;
    if (scenario === 'oversize-app') resolved.parts[0].data = new Uint8Array(0x260001);
    if (scenario === 'missing-app') resolved.parts = resolved.parts.slice(1);
    if (scenario === 'duplicate-app') resolved.parts.push(resolved.parts[0]);
    if (scenario === 'unknown-part') resolved.parts[0].name = 'unknown';
    if (scenario === 'missing-guard') resolved.requiredLayout = null;
    let mutations = 0;
    await assert.rejects(executeFlashPlan(resolved, {
      checkUpdate: p => checkLoaderUpdate(p, hardware(p, changes)),
      onState: () => {}, erase: async () => mutations++, write: async () => mutations++, verify: async () => {},
    }));
    assert.equal(mutations, 0);
  });
}

for (const id of ['heltec-v3', 'heltec-v4', 't147-lora-dualboot']) {
  test(`${id} checks its layout during preparation after select/download/connect`, async () => {
    const selected = catalog.devices.find(d => d.id === id);
    const resolved = await resolveFlashPlan(selected, 'update', fetchBytes);
    const calls = [];
    const flasher = {
      selectPort: async () => calls.push('port'),
      connect: async () => { calls.push('connect'); return { chipName: 'ESP32-S3' }; },
      checkChipFamily: () => calls.push('chip'),
      checkFlashSize: async () => calls.push('size'),
      checkUpdatePlan: async p => { assert.equal(p, resolved); calls.push('layout'); },
    };
    await prepareFlashSession({ flasher, device: selected, mode: 'update', resolvePlan: async () => {
      calls.push('download'); return resolved;
    } });
    assert.deepEqual(calls, ['port', 'download', 'connect', 'chip', 'size', 'layout']);
  });
}
