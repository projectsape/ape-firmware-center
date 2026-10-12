// Trust anchor is bundled with the app, never supplied by the downloaded catalog.
// Dedicated catalog key: generated on the owner's machine, never in CI, kept apart
// from the per-device OTA keys so each anchor rotates on its own. The catalog has
// its own signed domain; an OTA manifest signature cannot be reused as a catalog
// signature, and vice versa.
export const CATALOG_KEY_ID = 'ape-catalog-p256-v1';
export const CATALOG_ALGORITHM = 'ECDSA-P256-SHA256';
export const CATALOG_PUBLIC_KEY_SPKI =
  'MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAELEP5TVNeba5+szQ1JZpo5l7GoYDfasyGfAgLA70jChj3sfbAHYN2qw3MEBTg8WUzIj2x23+lL3a1VHEK1MQsUg==';

export function catalogSigningPayload(bytes) {
  const prefix = new TextEncoder().encode('APE-FIRMWARE-CATALOG-V1\n');
  const payload = new Uint8Array(prefix.length + bytes.length);
  payload.set(prefix);
  payload.set(bytes, prefix.length);
  return payload;
}

function decodeBase64(value) {
  return Uint8Array.from(atob(value), character => character.charCodeAt(0));
}

export async function verifyCatalogSignature(bytes, envelope) {
  if (!(bytes instanceof Uint8Array) || !envelope || envelope.schemaVersion !== 1 ||
      envelope.algorithm !== CATALOG_ALGORITHM || envelope.keyId !== CATALOG_KEY_ID ||
      Object.keys(envelope).sort().join(',') !== 'algorithm,keyId,schemaVersion,signature' ||
      typeof envelope.signature !== 'string' || envelope.signature.length > 128 ||
      !/^[A-Za-z0-9+/]+={0,2}$/.test(envelope.signature)) {
    throw new Error('Invalid firmware catalog signature metadata.');
  }
  const signature = decodeBase64(envelope.signature);
  // WebCrypto uses raw r || s (IEEE P1363), not the OTA manifest's DER encoding.
  if (signature.length !== 64) throw new Error('Invalid firmware catalog signature length.');
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) throw new Error('Catalog signature verification requires WebCrypto in a secure context.');
  const key = await subtle.importKey('spki', decodeBase64(CATALOG_PUBLIC_KEY_SPKI),
    { name: 'ECDSA', namedCurve: 'P-256' }, false, ['verify']);
  if (!await subtle.verify({ name: 'ECDSA', hash: 'SHA-256' }, key, signature, catalogSigningPayload(bytes))) {
    throw new Error('Firmware catalog signature verification failed. Nothing can be flashed.');
  }
}
