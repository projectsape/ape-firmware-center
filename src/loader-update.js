import { md5Hex } from './md5.js';
import { sha256Hex } from './sha256.js';

export class LoaderUpdateError extends Error {
  constructor(message, code = 'incompatible_layout') {
    super(message);
    this.code = code;
  }
}

// DualBoot USB updates write application slots and, when a release marks it
// changed, the loader slot. Every write is allowed only after comparing the
// installed partition table with the catalog artifact, so a device still on an
// older layout is refused instead of being converted behind the user's back.
const DEVICE_GUARDS = {
  't147-lora-dualboot': {
    layoutId: 'ape-t147-dualboot-ota-v2',
    slots: { wadamesh: 0x1a0000, meshtastic: 0x520000, loader: 0x20000 },
    capacity: { wadamesh: 0x380000, meshtastic: 0x400000, loader: 0x180000 },
    requiredApps: ['wadamesh', 'meshtastic'],
    flashSize: '16MB',
  },
  'heltec-v4': {
    layoutId: 'ape-heltec-v4-dualboot-ota-v1',
    slots: { meshcore: 0x1a0000, meshtastic: 0x3a0000, loader: 0x20000 },
    capacity: { meshcore: 0x200000, meshtastic: 0x300000, loader: 0x180000 },
    requiredApps: ['meshcore', 'meshtastic'],
    flashSize: '16MB',
  },
};

export function needsLoaderGuard(plan) {
  return Object.hasOwn(DEVICE_GUARDS, plan.deviceId) && plan.operation === 'update';
}

// Run at preparation AND at the write boundary; no cached approval survives a
// changed connection, plan, table or artifact. A full install has its own flow.
export async function checkLoaderUpdate(plan, hardware) {
  if (!needsLoaderGuard(plan)) return;
  const guard = DEVICE_GUARDS[plan.deviceId];
  const layout = plan.requiredLayout;
  if (plan.eraseAll !== false || plan.requireVerifiedFlashSize !== true ||
      plan.expectedFlashSize !== guard.flashSize || !Array.isArray(plan.parts) || !plan.parts.length ||
      layout?.id !== guard.layoutId || layout.address !== 0x8000 ||
      layout.size !== 4096 || !(layout.data instanceof Uint8Array) || layout.data.length !== 4096) {
    throw new LoaderUpdateError('Invalid DualBoot USB update plan.');
  }
  const seen = new Set();
  for (const part of plan.parts) {
    const name = part?.name;
    if (!Object.hasOwn(guard.slots, name) || seen.has(name) ||
        part.address !== guard.slots[name] ||
        !(part.data instanceof Uint8Array) || !part.data.length || part.data.length > guard.capacity[name]) {
      throw new LoaderUpdateError('Invalid DualBoot USB update plan.');
    }
    seen.add(name);
    if (await sha256Hex(part.data) !== String(part.sha256).toLowerCase()) {
      throw new LoaderUpdateError('Update artifacts changed after download.', 'verify_failed');
    }
  }
  if (!guard.requiredApps.every((name) => seen.has(name))) {
    throw new LoaderUpdateError('Invalid DualBoot USB update plan.');
  }
  if (await sha256Hex(layout.data) !== String(layout.sha256).toLowerCase()) {
    throw new LoaderUpdateError('Update artifacts changed after download.', 'verify_failed');
  }
  hardware.checkChipFamily('ESP32-S3', hardware.chipName);
  const size = await hardware.checkFlashSize(guard.flashSize);
  if (!size?.reliable || size.detectedFlashSize !== guard.flashSize) {
    throw new LoaderUpdateError('Cannot verify the required 16MB flash.', 'unverified_flash_size');
  }
  let installed;
  try {
    installed = await hardware.flashMd5sum(layout.address, layout.size);
  } catch {
    throw new LoaderUpdateError('Cannot read the installed DualBoot partition table.');
  }
  if (String(installed).trim().toLowerCase() !== md5Hex(layout.data)) {
    throw new LoaderUpdateError('This device does not have the OTA DualBoot layout. Use Clean install to convert it.');
  }
}

// Pure orchestration lets tests demonstrate that failed guards never erase or
// write, including when session preparation was bypassed.
export async function executeFlashPlan(plan, hooks) {
  await hooks.checkUpdate(plan);
  if (plan.eraseAll) {
    hooks.onState('erase');
    await hooks.erase();
  }
  hooks.onState('write');
  await hooks.write();
  hooks.onState('verify');
  await hooks.verify();
}
