import { md5Hex } from './md5.js';
import { sha256Hex } from './sha256.js';

export class LoaderUpdateError extends Error {
  constructor(message, code = 'incompatible_layout') {
    super(message);
    this.code = code;
  }
}

// The T147 DualBoot update writes the WadaMesh and Meshtastic application slots
// and, when a release marks it changed, the loader slot. Every write is allowed
// only after comparing the installed partition table with the catalog artifact.
const UPDATE_SLOTS = { wadamesh: 0x1a0000, meshtastic: 0x520000, loader: 0x20000 };
const UPDATE_CAPACITY = { wadamesh: 0x380000, meshtastic: 0x400000, loader: 0x180000 };
const REQUIRED_APPS = ['wadamesh', 'meshtastic'];

export function needsLoaderGuard(plan) {
  return plan.deviceId === 't147-lora-dualboot' && plan.operation === 'update';
}

// Run at preparation AND at the write boundary; no cached approval survives a
// changed connection, plan, table or artifact. A full install has its own flow.
export async function checkLoaderUpdate(plan, hardware) {
  if (!needsLoaderGuard(plan)) return;
  const layout = plan.requiredLayout;
  if (plan.eraseAll !== false || plan.requireVerifiedFlashSize !== true ||
      plan.expectedFlashSize !== '16MB' || !Array.isArray(plan.parts) || !plan.parts.length ||
      layout?.id !== 'ape-t147-dualboot-ota-v2' || layout.address !== 0x8000 ||
      layout.size !== 4096 || !(layout.data instanceof Uint8Array) || layout.data.length !== 4096) {
    throw new LoaderUpdateError('Invalid DualBoot USB update plan.');
  }
  const seen = new Set();
  for (const part of plan.parts) {
    const name = part?.name;
    if (!Object.hasOwn(UPDATE_SLOTS, name) || seen.has(name) ||
        part.address !== UPDATE_SLOTS[name] ||
        !(part.data instanceof Uint8Array) || !part.data.length || part.data.length > UPDATE_CAPACITY[name]) {
      throw new LoaderUpdateError('Invalid DualBoot USB update plan.');
    }
    seen.add(name);
    if (await sha256Hex(part.data) !== String(part.sha256).toLowerCase()) {
      throw new LoaderUpdateError('Update artifacts changed after download.', 'verify_failed');
    }
  }
  if (!REQUIRED_APPS.every((name) => seen.has(name))) {
    throw new LoaderUpdateError('Invalid DualBoot USB update plan.');
  }
  if (await sha256Hex(layout.data) !== String(layout.sha256).toLowerCase()) {
    throw new LoaderUpdateError('Update artifacts changed after download.', 'verify_failed');
  }
  hardware.checkChipFamily('ESP32-S3', hardware.chipName);
  const size = await hardware.checkFlashSize('16MB');
  if (!size?.reliable || size.detectedFlashSize !== '16MB') {
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
