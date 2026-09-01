// esptool-js flasher engine (FASE 4).
//
// Explicit control of the two install modes:
//   UPDATE -> writeFlash(...) with eraseAll = false  (never erase)
//   WIPE   -> eraseFlash() then writeFlash(...)      (full erase first)
//
// This engine NEVER inspects the existing firmware on the device. It only does
// a trivial chip-family check (selected target vs connected chip).

import { ESPLoader, Transport } from "esptool-js";
import { md5Hex } from "./md5.js";
import { attemptHardReset, calculateWriteProgress, chipFamilyMatches, flashSizeFromId, flashSizeMatches, resetAndMonitorTransport } from "./flash-flow.js";

export class FlasherError extends Error {
  constructor(message, code = "flash_failed", details = null) {
    super(message);
    this.name = "FlasherError";
    this.code = code;
    this.details = details;
  }
}

export class Flasher {
  constructor({ onLog = () => {} } = {}) {
    this.port = null;
    this.transport = null;
    this.loader = null;
    this.onLog = onLog;
    this.terminal = {
      clean: () => {},
      writeLine: (d) => this.onLog(d),
      write: (d) => this.onLog(d),
    };
  }

  static isSupported() {
    return typeof navigator !== "undefined" && "serial" in navigator;
  }

  // MUST be called directly from the user's click handler, before any fetch or
  // other awaited work. Browsers require transient user activation for the
  // Web Serial chooser.
  async selectPort() {
    if (!Flasher.isSupported()) {
      throw new FlasherError(
        "Web Serial is not supported in this browser.",
        "unsupported_browser"
      );
    }
    if (!this.port) this.port = await navigator.serial.requestPort();
    return this.port;
  }

  // Connect + detect chip. Returns { chipName, mac }. Does not inspect firmware.
  async connect() {
    if (!Flasher.isSupported()) {
      throw new FlasherError(
        "Web Serial is not supported in this browser.",
        "unsupported_browser"
      );
    }
    const port = this.port || await this.selectPort();
    this.transport = new Transport(port, true);
    this.loader = new ESPLoader({
      transport: this.transport,
      baudrate: 921600,
      terminal: this.terminal,
    });
    await this.loader.main();
    const chipName = this.loader.chip ? this.loader.chip.CHIP_NAME : "";
    let mac = "";
    try {
      mac = await this.loader.chip.readMac(this.loader);
    } catch {
      /* mac is optional */
    }
    return { chipName, mac };
  }

  // Basic, trivial chip-family check only (section 2 of the plan).
  checkChipFamily(expectedFamily, connectedChipName) {
    // CHIP_NAME is like "ESP32-S3"; compare the family token.
    if (!chipFamilyMatches(expectedFamily, connectedChipName)) {
      throw new FlasherError(
        `Wrong chip family: selected target ${expectedFamily}, connected chip ${connectedChipName || "unknown"}.`,
        "wrong_chip",
        { expectedFamily, connectedChipName }
      );
    }
  }

  // Compare the connected chip's physical flash size against the selected
  // device's declared size. This only signals "connected flash size does not
  // match the selected device" — it does NOT identify the board.
  //
  // We read the flash ID and look it up in DETECTED_FLASH_SIZES directly instead
  // of trusting detectFlashSize(), which silently defaults to "4MB" on unknown
  // IDs. A genuinely unknown flash size is NOT treated as a mismatch: we log a
  // warning and continue (no false block).
  async checkFlashSize(expectedFlashSize) {
    if (!this.loader) throw new FlasherError("Not connected.", "not_connected");
    const expected = String(expectedFlashSize || "").trim().toUpperCase();

    let detected = null;
    try {
      const flashId = await this.loader.readFlashId();
      detected = flashSizeFromId(flashId, this.loader.DETECTED_FLASH_SIZES);
    } catch (error) {
      this.onLog(`Unable to reliably verify physical flash size: ${error?.message || error}`);
    }

    if (!detected) {
      this.onLog("Unable to reliably verify physical flash size.");
      return { expectedFlashSize: expected || null, detectedFlashSize: null, reliable: false };
    }

    if (expected && !flashSizeMatches(expected, detected)) {
      throw new FlasherError(
        `Flash size mismatch: selected device expects ${expected}, connected flash is ${detected}.`,
        "wrong_flash_size",
        { expectedFlashSize: expected, detectedFlashSize: detected }
      );
    }
    return { expectedFlashSize: expected || null, detectedFlashSize: detected, reliable: true };
  }

  // Execute a resolved plan. States: "erase" (wipe only) -> "write" -> "verify".
  async flashPlan(plan, { onState = () => {}, onProgress = () => {} } = {}) {
    if (!this.loader) throw new FlasherError("Not connected.", "not_connected");

    if (plan.eraseAll) {
      onState("erase");
      await this.loader.eraseFlash();
    }

    onState("write");
    await this._write(plan.parts, onProgress);

    onState("verify");
    await this._verify(plan.parts, onProgress);
  }

  async _write(parts, onProgress) {
    const sizes = parts.map((p) => p.data.byteLength);

    await this.loader.writeFlash({
      fileArray: parts.map((p) => ({ data: p.data, address: p.address })),
      flashMode: "keep",
      flashFreq: "keep",
      flashSize: "keep",
      eraseAll: false, // erase (if any) already done explicitly above
      compress: true,
      reportProgress: (fileIndex, written, fileTotal) => {
        onProgress(calculateWriteProgress(sizes, fileIndex, written, fileTotal));
      },
    });
  }

  async _verify(parts, onProgress) {
    for (let i = 0; i < parts.length; i++) {
      const p = parts[i];
      const expected = md5Hex(p.data);
      const actual = await this.loader.flashMd5sum(p.address, p.data.byteLength);
      if (String(actual).trim().toLowerCase() !== expected.toLowerCase()) {
        throw new FlasherError(
          `Verification failed for "${p.name}" — flash contents do not match the firmware image.`,
          "verify_failed",
          { part: p.name, expected, actual: String(actual).trim() }
        );
      }
      onProgress((i + 1) / parts.length);
    }
  }

  async reset() {
    if (!this.loader) throw new FlasherError("Not connected.", "not_connected");
    return attemptHardReset(this.transport, { onLog: this.onLog });
  }

  async resetAndMonitor({ timeoutMs = 4000, onData = () => {} } = {}) {
    if (!this.loader || !this.transport || !this.port) {
      throw new FlasherError("Not connected.", "not_connected");
    }

    const port = this.port;
    try {
      // disconnect() cancels the active readLoop reader before waiting for its
      // lock. Calling waitForUnlock() first deadlocks on an idle serial port.
      await this.transport.disconnect();
    } catch (error) {
      this.onLog(`Could not switch to serial monitor: ${error?.message || error}`);
      return { resetPerformed: false, bootSeen: false };
    } finally {
      this.transport = null;
      this.loader = null;
    }

    const monitorTransport = new Transport(port, false, false);
    try {
      await monitorTransport.connect(115200);
      const result = await resetAndMonitorTransport(monitorTransport, {
        timeoutMs,
        onData,
        onLog: this.onLog,
      });
      this.port = null;
      return result;
    } catch (error) {
      this.onLog(`Serial monitor unavailable: ${error?.message || error}`);
      await monitorTransport.disconnect().catch(() => {});
      this.port = null;
      return { resetPerformed: false, bootSeen: false };
    }
  }

  async disconnect() {
    if (this.transport) {
      try {
        await this.transport.disconnect();
      } catch {
        /* ignore */
      }
    }
    this.transport = null;
    this.loader = null;
    this.port = null;
  }
}
