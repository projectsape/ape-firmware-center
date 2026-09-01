import { loadCatalog, getHardwareCards, resolveFlashPlan } from "./catalog.js";
import { Flasher, FlasherError } from "./flasher.js";
import { prepareFlashSession } from "./flash-flow.js";
import {
  el,
  shortHash,
  deviceName,
  buildDeviceCard,
  buildVariantGroupCard,
  buildWiringTable,
  buildCheckbox,
  buildProgressUI,
  updateProgressUI,
} from "./ui.js";

const app = {
  catalog: null,
  device: null,
  mode: null, // "update" | "wipe"
  wiringConfirmed: false,
  flasher: null,
  busy: false,
  webSerialSupported: Flasher.isSupported(),
};

// ---------------------------------------------------------------------------
// Modal management
// ---------------------------------------------------------------------------
const modal = document.getElementById("modal");
const modalBody = document.getElementById("modal-body");
let lastFocusedElement = null;

function setPageInert(inert) {
  document.querySelectorAll("body > :not(#modal):not(#toast)").forEach((node) => {
    node.inert = inert;
  });
}

function focusModalTitle() {
  requestAnimationFrame(() => document.getElementById("modal-title")?.focus());
}

function openModal() {
  lastFocusedElement = document.activeElement;
  modal.hidden = false;
  document.body.classList.add("modal-open");
  setPageInert(true);
  modalBody.scrollTop = 0;
  focusModalTitle();
}

function closeModal() {
  if (app.busy) return;
  modal.hidden = true;
  document.body.classList.remove("modal-open");
  setPageInert(false);
  if (app.flasher && !app.busy) {
    app.flasher.disconnect().catch(() => {});
    app.flasher = null;
  }
  if (lastFocusedElement?.isConnected) lastFocusedElement.focus();
}

function setModal(content, { title = null } = {}) {
  modalBody.replaceChildren(
    el("button", { class: "modal-close", "aria-label": "Close", onclick: closeModal }, "×"),
    title ? el("h2", { id: "modal-title", class: "modal-title", tabindex: "-1" }, title) : null,
    el("div", { class: "modal-content" }, content)
  );
  if (!modal.hidden) focusModalTitle();
}

function handleModalKeydown(e) {
  if (modal.hidden) return;
  if (e.key === "Escape") {
    closeModal();
    return;
  }
  if (e.key !== "Tab") return;

  const focusable = [...modal.querySelectorAll(
    'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
  )].filter((node) => node.offsetParent !== null && node.getAttribute("aria-hidden") !== "true");
  if (!focusable.length) {
    e.preventDefault();
    document.getElementById("modal-title")?.focus();
    return;
  }
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (e.shiftKey && (document.activeElement === first || !modal.contains(document.activeElement))) {
    e.preventDefault();
    last.focus();
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault();
    first.focus();
  }
}

// ---------------------------------------------------------------------------
// Views
// ---------------------------------------------------------------------------
function renderProvenance(provenance) {
  const entries = Object.entries(provenance || {});
  if (!entries.length) return null;

  const rows = entries.map(([component, item]) => {
    const name = component.charAt(0).toUpperCase() + component.slice(1);
    const commit = item.commit || null;
    return el("div", { class: "provenance-row" },
      el("strong", {}, name),
      el("span", {}, `Version ${item.version || "not recorded"}`),
      commit ? el("code", {}, `Commit ${commit}`) : null,
      item.source
        ? el("a", { href: item.source, target: "_blank", rel: "noopener" }, "Upstream source ›")
        : el("span", { class: "provenance-missing" }, "Source link not published")
    );
  });

  return el("section", { class: "provenance", "aria-labelledby": "provenance-title" },
    el("h3", { id: "provenance-title" }, "Source provenance"),
    el("p", { class: "provenance-intro" }, "Recorded build metadata from the firmware catalog. Missing values are shown as missing rather than inferred."),
    ...rows
  );
}

function getVariantGroupFor(device) {
  if (!device?.hardwareGroup) return null;
  const devices = (app.catalog?.devices || []).filter((candidate) => candidate.hardwareGroup === device.hardwareGroup);
  if (devices.length < 2) return null;
  return {
    id: device.hardwareGroup,
    displayName: device.hardwareGroupLabel || device.displayName || device.model,
    devices,
  };
}

function renderDetails(device) {
  const partsList = (plan, label) => {
    if (!plan) return null;
    return el("div", { class: "artifact-group" },
      el("div", { class: "artifact-label" }, label),
      ...plan.parts.map((p) =>
        el("div", { class: "artifact-row" },
          el("span", { class: "artifact-name" }, p.name),
          el("code", { class: "artifact-offset" }, p.offset),
          el("button", {
            class: "link-btn hash-btn",
            type: "button",
            title: "Copy SHA-256",
            "aria-label": `Copy catalog SHA-256 for ${p.name}`,
            "data-hash": p.sha256,
            onclick: (e) => copyHash(e),
          }, shortHash(p.sha256)),
          el("a", {
            class: "link-btn",
            href: `./${p.file}`,
            download: p.file.split("/").pop(),
            "aria-label": `Download ${p.name} firmware artifact`,
          }, "⬇ download")
        )
      )
    );
  };

  const meta = el("dl", { class: "detail-list" },
    el("dt", {}, "Manufacturer"), el("dd", {}, device.manufacturer),
    el("dt", {}, "Model"), el("dd", {}, device.model),
    device.variant ? el("dt", {}, "APE variant") : null, device.variant ? el("dd", {}, device.variant) : null,
    el("dt", {}, "Firmware"), el("dd", {}, device.firmware),
    el("dt", {}, "Meshtastic"), el("dd", {}, device.version),
    device.meshcoreVersion ? el("dt", {}, "MeshCore") : null, device.meshcoreVersion ? el("dd", {}, device.meshcoreVersion) : null,
    device.loaderVersion ? el("dt", {}, "Loader") : null, device.loaderVersion ? el("dd", {}, device.loaderVersion) : null,
    el("dt", {}, "Channel"), el("dd", {}, device.channel),
    el("dt", {}, "Release date"), el("dd", {}, device.releaseDate || "—"),
    el("dt", {}, "Chip"), el("dd", {}, device.chipModel || device.chipFamily),
    device.psramSize ? el("dt", {}, "PSRAM") : null, device.psramSize ? el("dd", {}, device.psramSize) : null,
    el("dt", {}, "Flash size"), el("dd", {}, device.flashSize),
    device.display ? el("dt", {}, "Display") : null, device.display ? el("dd", {}, device.display) : null,
  );

  const notes = device.releaseNotes
    ? el("div", { class: "notes" },
        el("h4", {}, "Release notes"),
        device.releaseNotes.whatsNew?.length ? el("p", { class: "notes-h" }, "What's new") : null,
        el("ul", {}, (device.releaseNotes.whatsNew || []).map((n) => el("li", {}, n))),
        device.releaseNotes.fixes?.length ? el("p", { class: "notes-h" }, "Fixes") : null,
        el("ul", {}, (device.releaseNotes.fixes || []).map((n) => el("li", {}, n))),
        device.releaseNotes.knownIssues?.length ? el("p", { class: "notes-h" }, "Known issues") : null,
        el("ul", {}, (device.releaseNotes.knownIssues || []).map((n) => el("li", {}, n)))
      )
    : null;

  const variantGroup = getVariantGroupFor(device);
  const selectedVariantBar = variantGroup
    ? el("div", { class: "selected-variant-bar" },
        el("span", {}, `${variantGroup.displayName.replace(/^APE\s+/i, "")} / ${device.variantLabel || device.variantKey || "Variant"} selected`),
        el("button", {
          class: "selected-variant-change",
          type: "button",
          onclick: () => {
            if (!app.busy) renderVariantPicker(variantGroup);
          },
        }, "Change variant")
      )
    : null;

  setModal(el("div", { class: "view-details" },
    selectedVariantBar,
    el("div", { class: "details-grid" },
      el("div", { class: "details-media" },
        el("img", { class: "modal-img", src: `./${device.image}`, alt: deviceName(device) })
      ),
      el("div", { class: "details-info" }, meta)
    ),
    el("div", { class: "artifacts" },
      partsList(device.factory, "Factory image"),
      partsList(device.update, "Update image")
    ),
    el("aside", { class: "integrity-explainer" },
      el("strong", {}, "SHA-256 download integrity"),
      el("p", {}, "Files are checked against the catalog before writing. This detects a corrupt or mismatched download; it is not a digital signature or independent proof of publisher identity.")
    ),
    renderProvenance(device.provenance),
    notes,
    el("div", { class: "modal-actions" },
      device.productUrl ? el("a", {
        class: "btn btn-ghost product-buy",
        href: device.productUrl,
        target: "_blank",
        rel: "noopener noreferrer sponsored",
      }, "Buy from Waveshare ↗") : null,
      app.webSerialSupported
        ? el("button", {
            class: "btn btn-primary",
            type: "button",
            onclick: () => goNext(device),
          }, device.requiresExternalRadio ? "Review wiring & continue" : "Flash this device")
        : el("button", {
            class: "btn btn-ghost",
            type: "button",
            onclick: () => renderCompatibilityHelp(device),
          }, "View compatibility help")
    )
  ), { title: deviceName(device) });
}

function selectDevice(device) {
  app.device = device;
  app.mode = null;
  app.wiringConfirmed = false;
  renderDetails(device);
}

function renderVariantPicker(group) {
  const options = group.devices.map((device) => {
    const isLoRa = device.variantKey === "lora" || device.requiresExternalRadio === true;
    return el("button", {
      class: `variant-option${isLoRa ? " variant-option-lora" : " variant-option-nolora"}`,
      type: "button",
      onclick: () => selectDevice(device),
    },
      el("span", { class: "variant-option-topline" },
        el("span", { class: "variant-option-name" }, isLoRa ? "LoRa" : "NoLoRa"),
        el("span", { class: "variant-option-code" }, isLoRa ? "SX1262" : "MQTT")
      ),
      el("span", { class: "variant-option-desc" }, isLoRa
        ? "External Wio / XIAO SX1262 required. Verify wiring before flashing."
        : "No SX1262 radio. Communicates over Wi-Fi via MQTT."),
      el("span", { class: "variant-option-action" }, isLoRa ? "Continue with LoRa →" : "Continue with NoLoRa →")
    );
  });

  setModal(el("div", { class: "view-variant-picker" },
    el("p", { class: "variant-picker-intro" }, "Choose the firmware that matches the radio hardware physically connected to your T147."),
    el("div", { class: "variant-option-grid" }, ...options),
    el("p", { class: "variant-picker-footnote" }, "You can change this selection from the firmware details until a flash operation starts.")
  ), { title: "Choose your T147 radio configuration" });
}

function goNext(device) {
  if (!app.webSerialSupported) {
    renderCompatibilityHelp(device);
    return;
  }
  if (device.requiresExternalRadio && !app.wiringConfirmed) {
    renderWiring(device);
  } else {
    renderMode(device);
  }
}

function renderCompatibilityHelp(device = null) {
  const openHelp = el("button", { class: "btn btn-primary", type: "button" }, "Open troubleshooting");
  openHelp.addEventListener("click", () => {
    closeModal();
    document.getElementById("help")?.scrollIntoView({ behavior: "smooth" });
  });

  setModal(el("div", { class: "compatibility-help" },
    el("div", { class: "warning" },
      el("p", {}, "Flashing is unavailable because this browser does not expose the Web Serial API.")
    ),
    el("p", {}, "Use current desktop Chrome or Microsoft Edge on ChromeOS, Linux, macOS or Windows. Connect the board with a USB data cable, then reopen this page."),
    el("p", {}, "The firmware details and direct downloads remain available here, but this browser cannot connect to the serial port."),
    el("a", {
      class: "reference-link",
      href: "https://developer.chrome.com/docs/capabilities/serial",
      target: "_blank",
      rel: "noopener",
    }, "Web Serial browser documentation ↗"),
    el("div", { class: "modal-actions" }, openHelp)
  ), { title: device ? `${deviceName(device)} — Browser compatibility` : "Browser compatibility" });
}

function renderWiring(device) {
  const wiring = device.wiring;
  const cb = buildCheckbox("ack-wiring", "I verified my Wio/XIAO SX1262 wiring.");
  cb.querySelector("input").addEventListener("change", (e) => {
    app.wiringConfirmed = e.target.checked;
    nextBtn.disabled = !e.target.checked;
  });
  const nextBtn = el("button", { class: "btn btn-primary", type: "button", disabled: "true" }, "Continue");
  nextBtn.addEventListener("click", () => renderMode(device));

  setModal(
    el("div", { class: "view-wiring" },
      el("p", { class: "wiring-note" }, wiring.note),
      buildWiringTable(wiring),
      wiring.antennaWarning ? el("p", { class: "warn-text" }, wiring.antennaWarning) : null,
      el("div", { class: "ack-list" }, cb),
      el("div", { class: "modal-actions" }, nextBtn)
    ),
    { title: `${deviceName(device)} — Wiring` }
  );
}

function renderMode(device) {
  const updateCard = el("button", { class: "mode-card mode-primary", type: "button", onclick: () => renderConfirm(device, "update") },
    el("span", { class: "mode-name" }, "UPDATE EXISTING APE"),
    el("span", { class: "mode-desc" }, "Writes only this target's update partitions without a full erase. Intended for the same APE layout; stored data is not guaranteed."),
    el("span", { class: "mode-badge" }, "No full erase")
  );
  const wipeCard = el("button", { class: "mode-card mode-danger", type: "button", onclick: () => renderConfirm(device, "wipe") },
    el("span", { class: "mode-name" }, "CLEAN INSTALL — ERASES ALL"),
    el("span", { class: "mode-desc" }, "Erases the entire flash, then installs the factory image. Firmware, settings and stored data are removed.")
  );

  setModal(
    el("div", { class: "view-mode" },
      el("p", { class: "mode-question" }, "HOW DO YOU WANT TO INSTALL?"),
      el("div", { class: "mode-grid" }, updateCard, wipeCard)
    ),
    { title: deviceName(device) }
  );
}

function renderConfirm(device, mode) {
  app.mode = mode;
  const isUpdate = mode === "update";

  const checks = [
    buildCheckbox("ack-hardware", `I verified that my hardware is ${deviceName(device)}.`),
    buildCheckbox("ack-experimental", "I understand that APE is experimental software provided without warranty."),
    buildCheckbox("ack-responsibility", "I accept responsibility for flashing my device."),
  ];
  if (device.requiresExternalRadio) {
    checks.push(buildCheckbox("ack-wiring2", "I verified the SX1262 wiring."));
  }
  if (!isUpdate) {
    checks.push(buildCheckbox("ack-erase", "I understand that all existing flash contents will be erased."));
  }

  const flashBtn = el("button", { class: "btn btn-primary btn-block", type: "button", disabled: "true" }, "Connect & Flash");
  const checkInputs = checks.map((c) => c.querySelector("input"));
  const syncEnabled = () => {
    flashBtn.disabled = !checkInputs.every((i) => i.checked);
  };
  checkInputs.forEach((i) => i.addEventListener("change", syncEnabled));

  flashBtn.addEventListener("click", () => runFlash(device, mode));

  const heading = isUpdate ? "UPDATE EXISTING APE" : "CLEAN INSTALL — ERASES ALL";
  const warning = isUpdate
    ? el("div", { class: "warning" },
        el("p", {}, "This writes only the declared update partitions; it does not perform a full flash erase."),
        el("p", {}, "It is intended for devices already running the corresponding APE firmware/layout."),
        el("p", {}, "Using this update over incompatible firmware may result in a device that does not boot and requires a clean reinstallation."),
        el("p", {}, "Existing data is not guaranteed against firmware bugs, power interruption, hardware faults or incompatible layouts.")
      )
    : el("div", { class: "warning" },
        el("p", {}, "This operation erases the entire device flash."),
        el("p", {}, "Existing firmware, configuration and stored data will be permanently removed.")
      );

  const disclaimer = el("div", { class: "disclaimer-box" },
    el("h4", {}, "EXPERIMENTAL SOFTWARE — USE AT YOUR OWN RISK"),
    el("p", {}, "APE firmware and Projects APE Flasher are experimental community projects provided free of charge. Firmware flashing carries inherent risks including configuration loss, data loss, failed boot, interrupted installation or the need to manually recover/reflash a device."),
    el("p", {}, "You are responsible for selecting the correct hardware, firmware, wiring and installation mode. The software and flashing service are provided \"as is\" without warranties of any kind.")
  );

  setModal(
    el("div", { class: "view-confirm" },
      el("h3", { class: "confirm-heading" }, heading),
      warning,
      disclaimer,
      el("div", { class: "ack-list" }, checks),
      el("div", { class: "modal-actions" }, flashBtn)
    ),
    { title: deviceName(device) }
  );
}

// ---------------------------------------------------------------------------
// Flash orchestration
// ---------------------------------------------------------------------------
async function runFlash(device, mode) {
  if (!app.webSerialSupported) {
    renderCompatibilityHelp(device);
    return;
  }
  if (app.busy) return;
  app.busy = true;
  modal.classList.add("busy");

  const ui = buildProgressUI();
  const { stateText, log } = ui;
  setModal(el("div", { class: "view-flash" },
    el("p", { class: "flash-banner" }, "FLASH IN PROGRESS — Do not disconnect USB."),
    ui.root
  ), { title: deviceName(device) });

  const setState = (state, pct = null) => {
    const labels = {
      preparing: "Preparing firmware…",
      "select-port": "Choose your USB device in the browser window…",
      connect: "Connecting to device…",
      erase: "Erasing device…",
      write: "Flashing…",
      verify: "Verifying written flash…",
      reset: "Resetting device and monitoring startup…",
      done: "Done",
    };
    stateText.textContent = labels[state] || state;
    if (pct !== null && Number.isFinite(pct)) {
      const p = updateProgressUI(ui, pct);
      stateText.textContent = `${labels[state] || state} ${p}%`;
    }
  };

  const logLine = (s) => {
    log.hidden = false;
    log.textContent += s + "\n";
    log.scrollTop = log.scrollHeight;
  };

  const flasher = new Flasher({ onLog: logLine });
  app.flasher = flasher;

  const showResult = (ok, title, body, details = null) => {
    app.busy = false;
    modal.classList.remove("busy");
    const back = el("button", { class: "btn btn-ghost", type: "button", onclick: () => closeModal() }, "Close");
    const content = el("div", { class: "result" },
      el("div", { class: `result-icon ${ok ? "ok" : "err"}` }, ok ? "✓" : "✕"),
      el("h3", { class: "result-title" }, title),
      el("p", { class: "result-body" }, body),
      details ? el("details", { class: "tech-details" },
        el("summary", {}, ok ? "Serial startup log" : "Technical details"),
        el("pre", {}, details)
      ) : null,
      el("div", { class: "modal-actions" }, back)
    );
    setModal(content, { title: deviceName(device) });
  };

  try {
    // This is deliberately the first awaited operation in the click flow:
    // Web Serial requires requestPort() while user activation is still live.
    const { plan } = await prepareFlashSession({
      flasher,
      device,
      mode,
      resolvePlan: resolveFlashPlan,
      onState: setState,
    });

    let currentState = "write";
    await flasher.flashPlan(plan, {
      onState: (s) => {
        currentState = s;
        setState(s);
      },
      onProgress: (p) => setState(currentState, p),
    });

    setState("reset");
    logLine("--- SERIAL MONITOR · 115200 BAUD ---");
    let serialOutput = "";
    const { resetPerformed, bootSeen } = await flasher.resetAndMonitor({
      timeoutMs: 4000,
      onData: (text) => {
        serialOutput += text;
        log.hidden = false;
        log.textContent += text;
        log.scrollTop = log.scrollHeight;
      },
    });
    app.flasher = null;

    setState("done", 1);
    if (mode === "update") {
      showResult(true, "UPDATE COMPLETE",
        bootSeen
          ? "Firmware was written and verified. Startup output was detected after the automatic reset."
          : resetPerformed
            ? "Firmware was written and verified, and the automatic reset was sent. No startup output was detected; press RESET if needed."
            : "Firmware was written and verified successfully. Press the device RESET button to start the new firmware.",
        serialOutput ? `Serial monitor (115200 baud):\n${serialOutput}` : null);
    } else {
      showResult(true, "CLEAN INSTALL COMPLETE",
        bootSeen
          ? "The device was erased and the new APE firmware was installed and verified. Startup output was detected after reset."
          : resetPerformed
            ? "The device was erased and the new APE firmware was installed and verified. The reset was sent; press RESET if it does not start."
            : "The device was erased and the new APE firmware was installed and verified successfully. Press the device RESET button to start it.",
        serialOutput ? `Serial monitor (115200 baud):\n${serialOutput}` : null);
    }
  } catch (err) {
    app.busy = false;
    const code = err instanceof FlasherError ? err.code : "flash_failed";
    const message = friendlyError(code, err);
    await flasher.disconnect().catch(() => {});
    app.flasher = null;
    const details = (err && (err.details ? JSON.stringify(err.details, null, 2) : (err.stack || String(err)))) || "";
    showResult(false, "Flash failed", message, details);
  }
}

function friendlyError(code, err) {
  const map = {
    unsupported_browser: "Browser not supported. Use a Web Serial compatible browser (Chrome or Edge) on a supported device.",
    wrong_chip: `Wrong chip family. You selected a ${err?.details?.expectedFamily || "target"} but the connected chip is ${err?.details?.connectedChipName || "different"}.`,
    wrong_flash_size: "Flash size mismatch — the connected flash does not match the selected device.",
    verify_failed: "Verification failed — the flash contents do not match the firmware image. Reconnect and try again.",
    not_connected: "Device not connected. Reconnect the board and try again.",
    flash_failed: "Flash failed. Reconnect the device and retry, or use Wipe & Install if the device no longer boots.",
  };
  if (code === "not_found") return "Device not found. Use a data-capable USB cable and reconnect the board.";
  if (err && err.message && /No port selected|user|abort|denied/i.test(err.message)) {
    return "No device selected. Try again and pick your board in the browser dialog.";
  }
  return map[code] || err?.message || "An unexpected error occurred.";
}

function copyHash(e) {
  const hash = e.currentTarget.dataset.hash;
  navigator.clipboard?.writeText(hash).then(
    () => toast("SHA-256 copied"),
    () => toast("Copy failed")
  );
}

function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (t.hidden = true), 1800);
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
function renderHardware(catalog) {
  const grid = document.getElementById("device-grid");
  grid.replaceChildren(...getHardwareCards(catalog).map((entry) => {
    const card = entry.type === "variant-group"
      ? buildVariantGroupCard(entry, { canFlash: app.webSerialSupported })
      : buildDeviceCard(entry.device, { canFlash: app.webSerialSupported });
    const open = () => {
      if (entry.type === "variant-group") renderVariantPicker(entry);
      else selectDevice(entry.device);
      openModal();
    };
    card.addEventListener("click", (event) => {
      // Let the "Buy from Waveshare" link follow its own href.
      if (event.target.closest("a")) return;
      open();
    });
    return card;
  }));
}

async function main() {
  // Browser support banner
  if (!app.webSerialSupported) {
    document.body.classList.add("serial-unsupported");
    const banner = el("div", { class: "browser-banner", role: "alert" },
      el("strong", {}, "Flashing unavailable in this browser."),
      el("span", {}, " Use desktop Chrome or Edge with a USB data cable. Device details and firmware downloads remain available. "),
      el("a", { href: "#help" }, "Compatibility help")
    );
    document.getElementById("top").prepend(banner);
  }

  try {
    app.catalog = await loadCatalog();
    renderHardware(app.catalog);
  } catch (err) {
    document.getElementById("device-grid").replaceChildren(
      el("p", { class: "error-text" }, `Failed to load the firmware catalog: ${err.message}`)
    );
  }

  // Modal keyboard + scroll-links
  document.addEventListener("keydown", handleModalKeydown);
  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeModal();
  });
  document.querySelectorAll("[data-scroll]").forEach((b) =>
    b.addEventListener("click", () => {
      document.querySelector(b.dataset.scroll)?.scrollIntoView({ behavior: "smooth" });
    })
  );
}

main();
