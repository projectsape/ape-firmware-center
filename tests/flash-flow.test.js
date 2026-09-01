import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { getHardwareCards, resolveFlashPlan } from "../src/catalog.js";
import { attemptHardReset, calculateWriteProgress, chipFamilyMatches, flashSizeFromId, flashSizeMatches, normalizeChipFamily, prepareFlashSession, resetAndMonitorTransport } from "../src/flash-flow.js";
import { sha256Hex } from "../src/sha256.js";
import { updateProgressUI } from "../src/ui.js";

const catalog = JSON.parse(await readFile(new URL("../public/data/firmware-catalog.json", import.meta.url)));

// sha256("abc")
const ABC_SHA256 = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";

// ---------------------------------------------------------------------------
// SHA-256
// ---------------------------------------------------------------------------

test("sha256Hex matches a known vector", async () => {
  assert.equal(await sha256Hex(new TextEncoder().encode("abc")), ABC_SHA256);
});

// ---------------------------------------------------------------------------
// Catalog structure (raw data, no fetch)
// ---------------------------------------------------------------------------

test("catalog: four devices; update never erases, factory always erases", () => {
  assert.equal(catalog.devices.length, 4);
  for (const d of catalog.devices) {
    assert.equal(d.update.eraseAll, false, `${d.id} update must not erase`);
    assert.equal(d.factory.eraseAll, true, `${d.id} factory must erase`);
    assert.ok(d.update.parts.length > 0, `${d.id} update parts`);
    assert.ok(d.factory.parts.length > 0, `${d.id} factory parts`);
    assert.ok(d.provenance && Object.keys(d.provenance).length > 0, `${d.id} provenance`);
    for (const [component, metadata] of Object.entries(d.provenance)) {
      assert.ok(metadata.version, `${d.id} ${component} provenance version`);
      assert.ok(metadata.source === null || metadata.source.startsWith("https://"), `${d.id} ${component} provenance source`);
    }
  }
});

test("hardware picker groups T147 LoRa and NoLoRa into one card without merging flash plans", () => {
  const cards = getHardwareCards(catalog);
  assert.equal(cards.length, 3);
  assert.deepEqual(cards.map((card) => card.id || card.device.id), ["heltec-v3", "heltec-v4", "t147"]);

  const t147 = cards.find((card) => card.id === "t147");
  assert.equal(t147.type, "variant-group");
  assert.deepEqual(t147.devices.map((device) => device.id), ["t147-lora", "t147-nolora"]);
  assert.notEqual(t147.devices[0].update.parts[0].file, t147.devices[1].update.parts[0].file);
});

test("hardware grouping uses explicit metadata and never swallows a similarly named target", () => {
  const extra = { id: "t147-future", displayName: "Future T147 target" };
  const cards = getHardwareCards({ devices: [...catalog.devices, extra] });
  assert.equal(cards.length, 4);
  assert.equal(cards.at(-1).type, "device");
  assert.equal(cards.at(-1).device.id, "t147-future");
});

test("updateProgressUI updates the visible fill, exposes percent and clamps input", () => {
  const attrs = new Map();
  const ui = {
    fill: { style: {} },
    bar: { setAttribute: (name, value) => attrs.set(name, value) },
  };

  assert.equal(updateProgressUI(ui, 0.426), 43);
  assert.equal(ui.fill.style.width, "43%");
  assert.equal(attrs.get("aria-valuenow"), "43");

  assert.equal(updateProgressUI(ui, 1.5), 100);
  assert.equal(ui.fill.style.width, "100%");
  assert.equal(updateProgressUI(ui, -0.2), 0);
  assert.equal(updateProgressUI(ui, Number.NaN), null);
});

test("compressed writes map per-file transfer progress to the complete flash plan", () => {
  const sizes = [1_000, 9_000];

  // The original parts total 10,000 bytes, while esptool-js reports compressed
  // transfer totals of 100 and 900 bytes for the two files.
  assert.equal(calculateWriteProgress(sizes, 0, 50, 100), 0.05);
  assert.equal(calculateWriteProgress(sizes, 0, 100, 100), 0.1);
  assert.equal(calculateWriteProgress(sizes, 1, 450, 900), 0.55);
  assert.equal(calculateWriteProgress(sizes, 1, 900, 900), 1);
});

// ---------------------------------------------------------------------------
// resolveFlashPlan: structure + SHA-256 integrity (download == catalog)
// ---------------------------------------------------------------------------

function synthDevice(overrides = {}) {
  return {
    id: "synth",
    update: { eraseAll: false, parts: [{ name: "app", file: "app.bin", offset: "0x10000", sha256: ABC_SHA256 }] },
    factory: { eraseAll: true, parts: [] },
    ...overrides,
  };
}
const abcBytes = () => new TextEncoder().encode("abc");

test("resolveFlashPlan verifies SHA-256 and aborts on mismatch before any write", async () => {
  const device = synthDevice();
  const update = await resolveFlashPlan(device, "update", abcBytes);
  assert.equal(update.eraseAll, false);
  assert.equal(update.parts.length, 1);
  assert.equal(update.parts[0].address, 0x10000);

  // Tampered bytes must abort with a clear SHA-256 error.
  const tampered = async () => new Uint8Array([1, 2, 3]);
  await assert.rejects(resolveFlashPlan(device, "update", tampered), /SHA-256 mismatch/);
});

test("resolveFlashPlan wipes map to factory plan and verify integrity", async () => {
  const bytes = new TextEncoder().encode("abc");
  const sha = await sha256Hex(bytes);
  const device = {
    id: "synth",
    update: { eraseAll: false, parts: [] },
    factory: { eraseAll: true, parts: [{ name: "factory", file: "factory.bin", offset: "0x0", sha256: sha }] },
  };
  const plan = await resolveFlashPlan(device, "wipe", async () => bytes);
  assert.equal(plan.eraseAll, true);
  assert.equal(plan.parts.length, 1);
});

// ---------------------------------------------------------------------------
// loaderChanged
// ---------------------------------------------------------------------------

test("loaderChanged=false omits loader from update plan", async () => {
  const device = synthDevice({
    loader: { file: "loader.bin", offset: "0x20000", sha256: ABC_SHA256 },
    update: { eraseAll: false, loaderChanged: false, parts: [{ name: "app", file: "app.bin", offset: "0x10000", sha256: ABC_SHA256 }] },
  });
  const plan = await resolveFlashPlan(device, "update", abcBytes);
  assert.deepEqual(plan.parts.map((p) => p.name), ["app"]);
});

test("loaderChanged=true includes loader in update plan at its offset", async () => {
  const device = synthDevice({
    loader: { file: "loader.bin", offset: "0x20000", sha256: ABC_SHA256 },
    update: { eraseAll: false, loaderChanged: true, parts: [{ name: "app", file: "app.bin", offset: "0x10000", sha256: ABC_SHA256 }] },
  });
  const plan = await resolveFlashPlan(device, "update", abcBytes);
  assert.deepEqual(plan.parts.map((p) => p.name), ["app", "loader"]);
  const loader = plan.parts.find((p) => p.name === "loader");
  assert.equal(loader.address, 0x20000);
});

test("loaderChanged=true with wrong loader sha fails (SHA-256 mismatch)", async () => {
  const device = synthDevice({
    loader: { file: "loader.bin", offset: "0x20000", sha256: "deadbeef" },
    update: { eraseAll: false, loaderChanged: true, parts: [{ name: "app", file: "app.bin", offset: "0x10000", sha256: ABC_SHA256 }] },
  });
  await assert.rejects(resolveFlashPlan(device, "update", abcBytes), /SHA-256 mismatch/);
});

// ---------------------------------------------------------------------------
// chip family — strict equality after normalization
// ---------------------------------------------------------------------------

test("normalizeChipFamily strips punctuation and uppercases", () => {
  assert.equal(normalizeChipFamily("ESP32-S3"), "ESP32S3");
  assert.equal(normalizeChipFamily("esp32s3"), "ESP32S3");
  assert.equal(normalizeChipFamily(""), "");
});

test("chipFamilyMatches uses strict equality (no substring)", () => {
  assert.equal(chipFamilyMatches("ESP32-S3", "ESP32-S3"), true);
  assert.equal(chipFamilyMatches("ESP32-S3", "ESP32S3"), true);
  assert.equal(chipFamilyMatches("ESP32", "ESP32S3"), false);
  assert.equal(chipFamilyMatches("ESP32S2", "ESP32S3"), false);
  assert.equal(chipFamilyMatches("ESP32-S3", "UNKNOWN"), false);
  assert.equal(chipFamilyMatches("ESP32-S3", ""), false);
  assert.equal(chipFamilyMatches("", "ESP32-S3"), false);
});

// ---------------------------------------------------------------------------
// flash size
// ---------------------------------------------------------------------------

test("flashSizeMatches compares normalized sizes", () => {
  assert.equal(flashSizeMatches("16MB", "16MB"), true);
  assert.equal(flashSizeMatches("16mb", "16MB"), true);
  assert.equal(flashSizeMatches("8MB", "16MB"), false);
  assert.equal(flashSizeMatches("16MB", "8MB"), false);
  assert.equal(flashSizeMatches("", "16MB"), false);
  assert.equal(flashSizeMatches("16MB", ""), false);
});

test("flashSizeFromId returns the size for a recognized ID, null for unknown", () => {
  const map = { 0x17: "8MB", 0x18: "16MB" };
  assert.equal(flashSizeFromId(0x18 << 16, map), "16MB");
  assert.equal(flashSizeFromId(0x17 << 16, map), "8MB");
  assert.equal(flashSizeFromId(0x99 << 16, map), null); // unknown size ID -> not a fallback
  assert.equal(flashSizeFromId(null, map), null);
  assert.equal(flashSizeFromId(undefined, map), null);
});

// ---------------------------------------------------------------------------
// prepareFlashSession ordering
// ---------------------------------------------------------------------------

test("USB port selection happens before firmware download and connection", async () => {
  const calls = [];
  const flasher = {
    async selectPort() { calls.push("select-port"); },
    async connect() { calls.push("connect"); return { chipName: "ESP32-S3" }; },
    checkChipFamily() { calls.push("chip-check"); },
  };
  const resolvePlan = async () => {
    calls.push("download-plan");
    return { eraseAll: true, parts: [] };
  };
  await prepareFlashSession({ flasher, device: { chipFamily: "ESP32-S3" }, mode: "wipe", resolvePlan });
  assert.deepEqual(calls, ["select-port", "download-plan", "connect", "chip-check"]);
});

test("prepareFlashSession checks flash size after chip family when declared", async () => {
  const calls = [];
  const flasher = {
    async selectPort() { calls.push("select-port"); },
    async connect() { calls.push("connect"); return { chipName: "ESP32-S3" }; },
    checkChipFamily() { calls.push("chip-check"); },
    async checkFlashSize() { calls.push("flash-size"); },
  };
  const resolvePlan = async () => ({ eraseAll: true, parts: [] });
  await prepareFlashSession({ flasher, device: { chipFamily: "ESP32-S3", flashSize: "16MB" }, mode: "wipe", resolvePlan });
  assert.deepEqual(calls, ["select-port", "connect", "chip-check", "flash-size"]);
});

// ---------------------------------------------------------------------------
// reset / serial monitor
// ---------------------------------------------------------------------------

test("hard reset releases IO0, pulses EN and reports success", async () => {
  const calls = [];
  const transport = {
    async setDTR(value) { calls.push(["DTR", value]); },
    async setRTS(value) { calls.push(["RTS", value]); },
  };
  const reset = await attemptHardReset(transport, { sleepFn: async (ms) => calls.push(["WAIT", ms]) });
  assert.equal(reset, true);
  assert.deepEqual(calls, [
    ["DTR", false], ["RTS", true], ["WAIT", 100],
    ["RTS", false], ["WAIT", 100],
  ]);
});

test("reset-line failure is non-fatal after a verified flash", async () => {
  const logs = [];
  const transport = {
    async setDTR() { throw new Error("signals unsupported"); },
    async setRTS() {},
  };
  const reset = await attemptHardReset(transport, { onLog: (line) => logs.push(line) });
  assert.equal(reset, false);
  assert.match(logs[0], /signals unsupported/);
});

test("serial monitor captures startup output after reset", async () => {
  const calls = [];
  const output = [];
  const transport = {
    async setDTR(value) { calls.push(["DTR", value]); },
    async setRTS(value) { calls.push(["RTS", value]); },
    async rawRead(onData) {
      onData(new TextEncoder().encode("ESP-ROM:esp32s3\nAPE boot\n"));
    },
    async disconnect() { calls.push(["DISCONNECT"]); },
  };
  const result = await resetAndMonitorTransport(transport, {
    timeoutMs: 10,
    sleepFn: async () => {},
    onData: (text) => output.push(text),
  });
  assert.deepEqual(result, { resetPerformed: true, bootSeen: true });
  assert.match(output.join(""), /APE boot/);
  assert.ok(calls.some(([name]) => name === "DISCONNECT"));
});
