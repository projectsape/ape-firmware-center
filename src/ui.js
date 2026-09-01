// Small DOM helpers + templates. No framework.

export function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (k === "class") node.className = v;
    else if (k === "dataset") Object.assign(node.dataset, v);
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else if (k === "value") node.value = v;
    else if (v === true) node.setAttribute(k, "");
    else if (v !== false && v !== null && v !== undefined) node.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

export function formatBytes(n) {
  if (!Number.isFinite(n)) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(v >= 100 || i === 0 ? 0 : 1)} ${units[i]}`;
}

export function shortHash(hash) {
  if (!hash) return "—";
  if (hash.length <= 16) return hash;
  return `${hash.slice(0, 8)}…${hash.slice(-8)}`;
}

export function deviceName(device) {
  return device.displayName || `${device.manufacturer} ${device.model}`;
}

const boardImageDimensions = {
  "assets/boards/heltec-v3.webp": [800, 800],
  "assets/boards/heltec-v4.webp": [800, 800],
  "assets/boards/t147.webp": [1024, 784],
};

export function buildDeviceCard(device, { canFlash = true } = {}) {
  const needsWiring = device.requiresExternalRadio === true;
  const subtitle = device.displayName ? `${device.manufacturer} ${device.model}` : (needsWiring ? "External SX1262" : device.firmware);
  const action = canFlash ? (needsWiring ? "Wiring & Flash" : "View & Flash") : "View details";
  const [imageWidth, imageHeight] = boardImageDimensions[device.image] || [];

  const img = el("img", {
    class: "card-img",
    src: `./${device.image}`,
    alt: `${deviceName(device)} — ${device.firmware}`,
    loading: "lazy",
    width: imageWidth,
    height: imageHeight,
  });

  return el(
    "article",
    { class: "device-card", dataset: { id: device.id } },
    el("div", { class: "card-media" },
      el("span", { class: "card-vendor" }, device.manufacturer.toUpperCase()),
      img,
      el("span", { class: "card-open", "aria-hidden": "true" }, "↗")
    ),
    el("div", { class: "card-body" },
      el("div", { class: "card-heading" },
        el("h3", { class: "card-title" }, deviceName(device)),
        el("span", { class: "card-channel" }, device.channel)
      ),
      el("p", { class: "card-subtitle" }, subtitle),
      device.variant ? el("p", { class: `card-variant${needsWiring ? " card-variant-radio" : ""}` }, device.variant) : null,
      el("div", { class: "card-meta" },
        el("span", { class: "chip" }, device.chipModel || device.chipFamily),
        device.psramSize ? el("span", { class: "chip chip-dim" }, `${device.psramSize} PSRAM`) : null,
        el("span", { class: "chip chip-dim" }, device.flashSize)
      ),
      device.productUrl ? el("a", {
        class: "product-link",
        href: device.productUrl,
        target: "_blank",
        rel: "noopener noreferrer sponsored",
      }, "Buy from Waveshare", el("span", { "aria-hidden": "true" }, "↗")) : null,
      el("button", { class: "btn btn-card btn-block card-action", type: "button" }, action, el("span", { "aria-hidden": "true" }, "→"))
    )
  );
}

export function buildVariantGroupCard(group, { canFlash = true } = {}) {
  const device = group.devices[0];
  const [imageWidth, imageHeight] = boardImageDimensions[device.image] || [];
  const variants = group.devices.map((item) => item.requiresExternalRadio ? "LoRa" : "NoLoRa");

  return el(
    "article",
    { class: "device-card device-card-group", dataset: { id: group.id } },
    el("div", { class: "card-media" },
      el("span", { class: "card-vendor" }, device.manufacturer.toUpperCase()),
      el("img", {
        class: "card-img",
        src: `./${device.image}`,
        alt: `${group.displayName} — choose LoRa or NoLoRa firmware`,
        loading: "lazy",
        width: imageWidth,
        height: imageHeight,
      }),
      el("span", { class: "card-open", "aria-hidden": "true" }, "2 MODES")
    ),
    el("div", { class: "card-body" },
      el("div", { class: "card-heading" },
        el("h3", { class: "card-title" }, group.displayName),
        el("span", { class: "card-channel" }, device.channel)
      ),
      el("p", { class: "card-subtitle" }, `${device.manufacturer} ${device.model}`),
      el("div", { class: "variant-pills", "aria-label": "Available firmware variants" },
        ...variants.map((variant) => el("span", { class: `variant-pill variant-pill-${variant.toLowerCase()}` }, variant))
      ),
      el("p", { class: "card-variant" }, "Choose the radio configuration before viewing or flashing firmware."),
      el("div", { class: "card-meta" },
        el("span", { class: "chip" }, device.chipModel || device.chipFamily),
        device.psramSize ? el("span", { class: "chip chip-dim" }, `${device.psramSize} PSRAM`) : null,
        el("span", { class: "chip chip-dim" }, device.flashSize)
      ),
      device.productUrl ? el("a", {
        class: "product-link",
        href: device.productUrl,
        target: "_blank",
        rel: "noopener noreferrer sponsored",
      }, "Buy from Waveshare", el("span", { "aria-hidden": "true" }, "↗")) : null,
      el("button", { class: "btn btn-card btn-block card-action", type: "button" },
        canFlash ? "Choose LoRa / NoLoRa" : "Choose variant",
        el("span", { "aria-hidden": "true" }, "→")
      )
    )
  );
}

export function buildWiringTable(wiring) {
  const rows = (wiring.pins || []).map((p) =>
    el("tr", {},
      el("td", { class: "wiring-from" }, p.from),
      el("td", { class: "wiring-arrow", "aria-hidden": "true" }, "→"),
      el("td", { class: "wiring-to" }, p.to)
    )
  );
  const table = el("table", { class: "wiring-table" },
    el("caption", { class: "sr-only" }, wiring.title || "Radio wiring connections"),
    el("thead", {},
      el("tr", {},
        el("th", { scope: "col" }, "Wio / XIAO SX1262"),
        el("th", { scope: "col", class: "wiring-arrow", "aria-label": "connects to" }, "→"),
        el("th", { scope: "col" }, "Waveshare T147")
      )
    ),
    el("tbody", {}, rows)
  );
  return table;
}

export function buildCheckbox(id, label) {
  const input = el("input", { type: "checkbox", id, class: "ack-check" });
  return el("label", { class: "ack-row", for: id },
    input,
    el("span", { class: "ack-label" }, label)
  );
}

export function buildProgressUI() {
  const fill = el("div", { class: "progress-fill" });
  const bar = el("div", {
    class: "progress",
    role: "progressbar",
    "aria-label": "Firmware flashing progress",
    "aria-valuemin": "0",
    "aria-valuemax": "100",
    "aria-valuenow": "0",
  },
    fill
  );
  const stateText = el("div", {
    class: "progress-state",
    role: "status",
    "aria-live": "polite",
    "aria-atomic": "true",
  }, "Preparing…");
  const log = el("pre", { class: "flash-log", hidden: "true" });
  return { root: el("div", { class: "flash-progress" }, bar, stateText, log), bar, fill, stateText, log };
}

export function updateProgressUI(ui, fraction) {
  if (!Number.isFinite(fraction)) return null;
  const percent = Math.round(Math.min(1, Math.max(0, fraction)) * 100);
  ui.fill.style.width = `${percent}%`;
  ui.bar.setAttribute("aria-valuenow", String(percent));
  return percent;
}
