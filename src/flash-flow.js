// Connection preparation is isolated so its ordering can be unit-tested.
// requestPort() MUST be the first awaited operation after the user's click.

// Normalize chip-family tokens to a comparable form ("ESP32-S3" -> "ESP32S3").
export function normalizeChipFamily(value) {
  return String(value || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
}

// Strict equality after normalization (no substring matching). Unknown/empty
// values never match, so an unrecognized chip fails closed.
export function chipFamilyMatches(expectedFamily, connectedChipName) {
  const expected = normalizeChipFamily(expectedFamily);
  const actual = normalizeChipFamily(connectedChipName);
  if (!expected || !actual) return false;
  return expected === actual;
}

// Compare a detected physical flash size (e.g. "16MB") against the selected
// device's declared size. Pure, so it can be unit-tested without esptool.
export function flashSizeMatches(expectedFlashSize, detectedFlashSize) {
  const expected = String(expectedFlashSize || "").trim().toUpperCase();
  const actual = String(detectedFlashSize || "").trim().toUpperCase();
  if (!expected || !actual) return false;
  return expected === actual;
}

// Map a raw SPI flash ID to a size string using esptool's DETECTED_FLASH_SIZES
// table. Returns null when the size ID is not recognized (so callers can tell
// "reliably detected" from "unknown/fallback" instead of trusting a "4MB" default).
export function flashSizeFromId(flashId, sizeMap) {
  if (typeof flashId !== "number") return null;
  const sizeId = (flashId >> 16) & 0xff;
  return (sizeMap && sizeMap[sizeId]) || null;
}

// esptool-js reports compressed transfer bytes when write compression is on.
// Reweight that per-file fraction using the original part sizes so the UI
// represents progress across the complete (uncompressed) flash plan.
export function calculateWriteProgress(sizes, fileIndex, written, fileTotal) {
  const normalizedSizes = sizes.map((size) => Math.max(0, Number(size) || 0));
  const totalBytes = normalizedSizes.reduce((sum, size) => sum + size, 0);
  if (totalBytes === 0) return 1;

  const index = Number.isInteger(fileIndex) && fileIndex >= 0 && fileIndex < normalizedSizes.length
    ? fileIndex
    : 0;
  const completedBytes = normalizedSizes.slice(0, index).reduce((sum, size) => sum + size, 0);
  const fileFraction = Number.isFinite(written) && Number.isFinite(fileTotal) && fileTotal > 0
    ? Math.min(1, Math.max(0, written / fileTotal))
    : 0;

  return Math.min(1, Math.max(0,
    (completedBytes + (normalizedSizes[index] * fileFraction)) / totalBytes
  ));
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// ESP32-S3 cannot use ESPLoader.softReset() while its flasher stub is running.
// A reset-line failure is non-fatal: a verified flash remains successful and
// the user can press the physical RESET button.
export async function attemptHardReset(transport, { sleepFn = sleep, onLog = () => {} } = {}) {
  try {
    // IO0 released/high, EN low, then EN high: boot the flashed application.
    await transport.setDTR(false);
    await transport.setRTS(true);
    await sleepFn(100);
    await transport.setRTS(false);
    await sleepFn(100);
    return true;
  } catch (error) {
    onLog(`Automatic reset unavailable: ${error?.message || error}`);
    return false;
  }
}

export async function resetAndMonitorTransport(
  transport,
  { timeoutMs = 4000, sleepFn = sleep, onData = () => {}, onLog = () => {} } = {}
) {
  let closed = false;
  let bootSeen = false;
  const decoder = new TextDecoder();
  const readPromise = transport.rawRead(
    (data) => {
      const text = decoder.decode(data, { stream: true });
      if (text) {
        bootSeen = true;
        onData(text);
      }
    },
    () => closed
  ).catch((error) => onLog(`Serial monitor stopped: ${error?.message || error}`));

  const resetPerformed = await attemptHardReset(transport, { sleepFn, onLog });
  await sleepFn(timeoutMs);
  closed = true;
  await transport.disconnect().catch((error) =>
    onLog(`Serial monitor close warning: ${error?.message || error}`)
  );
  await Promise.race([readPromise, sleepFn(250)]);
  return { resetPerformed, bootSeen };
}

export async function prepareFlashSession({ flasher, device, mode, resolvePlan, onState = () => {} }) {
  onState("select-port");
  await flasher.selectPort();

  onState("preparing");
  const plan = await resolvePlan(device, mode);

  onState("connect");
  const connection = await flasher.connect();
  flasher.checkChipFamily(device.chipFamily, connection.chipName);
  if (device.flashSize) {
    await flasher.checkFlashSize(device.flashSize);
  }

  return { plan, connection };
}
