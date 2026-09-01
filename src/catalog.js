// Catalog loading + firmware fetching. All paths are relative to the page so the
// site works under GitHub Pages subpath and any future custom domain.

import { sha256Hex } from "./sha256.js";

let catalogPromise = null;

export function loadCatalog() {
  if (!catalogPromise) {
    // The catalog is small and decides which firmware gets downloaded, so it is
    // always fetched fresh (never a stale cached copy).
    catalogPromise = fetch(new URL("./data/firmware-catalog.json", document.baseURI), {
      cache: "no-store",
    }).then((res) => {
      if (!res.ok) throw new Error(`Failed to load firmware catalog (HTTP ${res.status})`);
      return res.json();
    });
  }
  return catalogPromise;
}

export function getDevices(catalog) {
  return catalog.devices || [];
}

// The firmware catalog remains one-entry-per-flash-target, but the hardware
// picker can group targets that share the same physical board. Grouping is
// explicit catalog metadata so a future T147 target cannot disappear merely
// because its ID happens to share a prefix.
export function getHardwareCards(catalog) {
  const devices = getDevices(catalog);
  const emittedGroups = new Set();
  const cards = [];

  for (const device of devices) {
    if (!device.hardwareGroup) {
      cards.push({ type: "device", device });
      continue;
    }

    if (emittedGroups.has(device.hardwareGroup)) continue;
    emittedGroups.add(device.hardwareGroup);
    const variants = devices.filter((candidate) => candidate.hardwareGroup === device.hardwareGroup);

    if (variants.length < 2) {
      cards.push({ type: "device", device });
      continue;
    }

    cards.push({
      type: "variant-group",
      id: device.hardwareGroup,
      displayName: device.hardwareGroupLabel || device.displayName || device.model,
      devices: variants,
    });
  }

  return cards;
}

export function getDevice(catalog, id) {
  return (catalog.devices || []).find((d) => d.id === id) || null;
}

export async function fetchFirmwareBytes(file) {
  const url = new URL("./" + file, document.baseURI);
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch "${file}" (HTTP ${res.status})`);
  const buf = await res.arrayBuffer();
  return new Uint8Array(buf);
}

export function parseOffset(offset) {
  if (typeof offset === "number") return offset;
  return parseInt(String(offset).replace(/^0x/i, ""), 16);
}

// Build a concrete flash plan { eraseAll, parts: [{name, address, sha256, data}] }.
// Every downloaded artifact is SHA-256 checked against the catalog BEFORE any
// flash write. A mismatch aborts the plan (nothing is written).
export async function resolveFlashPlan(device, mode, fetchBytes = fetchFirmwareBytes) {
  // UI mode "wipe" maps to the catalog's "factory" plan; "update" stays as-is.
  const planKey = mode === "wipe" ? "factory" : mode;
  const plan = device[planKey];
  if (!plan || !Array.isArray(plan.parts)) {
    throw new Error(`No ${planKey} flash plan defined for ${device.id}`);
  }

  const partsSpec = plan.parts.slice();
  // The loader is only part of an UPDATE when the release marks it changed.
  if (planKey === "update" && device.loader && plan.loaderChanged === true) {
    partsSpec.push({
      name: "loader",
      file: device.loader.file,
      offset: device.loader.offset,
      sha256: device.loader.sha256,
    });
  }

  const parts = [];
  for (const part of partsSpec) {
    const data = await fetchBytes(part.file);
    const actual = await sha256Hex(data);
    const expected = String(part.sha256 || "").toLowerCase();
    if (actual.toLowerCase() !== expected) {
      throw new Error(
        `SHA-256 mismatch for "${part.file}" (catalog ${part.sha256}, downloaded ${actual}).`
      );
    }
    parts.push({
      name: part.name,
      file: part.file,
      address: parseOffset(part.offset),
      sha256: part.sha256,
      data,
    });
  }
  return { eraseAll: Boolean(plan.eraseAll), parts };
}
