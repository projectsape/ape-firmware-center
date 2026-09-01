// SHA-256 via the Web Crypto API. Available in secure contexts (HTTPS,
// localhost) and in Node >= 19 (globalThis.crypto.subtle).
// Used to verify downloaded firmware against the SHA-256 declared in
// firmware-catalog.json BEFORE any flash write.

export async function sha256Hex(data) {
  const bytes = data instanceof Uint8Array ? data : new Uint8Array(data);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  const view = new Uint8Array(digest);
  let hex = "";
  for (let i = 0; i < view.length; i++) {
    hex += view[i].toString(16).padStart(2, "0");
  }
  return hex;
}
