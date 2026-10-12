#!/usr/bin/env node
// Offline signing / public-only verification. Never provision keys in CI.
import { readFile, writeFile } from 'node:fs/promises';
import { createPrivateKey, createPublicKey, sign } from 'node:crypto';
import { resolve, join } from 'node:path';
import { CATALOG_KEY_ID, CATALOG_ALGORITHM, CATALOG_PUBLIC_KEY_SPKI,
  catalogSigningPayload, verifyCatalogSignature } from '../src/catalog-signature.js';
import { fileURLToPath } from 'node:url';

const [mode, directory = 'public', keyFile] = process.argv.slice(2);
const USAGE = `Usage:
  node ${fileURLToPath(import.meta.url)} verify [public|dist]
  node ${fileURLToPath(import.meta.url)} sign public /private/path/key.pem`;
try {
  if (!['sign', 'verify'].includes(mode)) throw new Error(`Unknown mode ${mode === undefined ? '(none)' : `"${mode}"`}.\n${USAGE}`);
  if (mode === 'verify' && keyFile) throw new Error(`verify never takes a key.\n${USAGE}`);
  if (mode === 'sign' && !keyFile) throw new Error(`signing requires the production P-256 private key.\n${USAGE}`);
  if (process.argv.slice(2).length > 3) throw new Error(`Too many arguments.\n${USAGE}`);
  const root = resolve(directory);
  const catalog = await readFile(join(root, 'data/firmware-catalog.json'));
  const signaturePath = join(root, 'data/firmware-catalog.sig.json');
  let envelope;
  if (mode === 'sign') {
    const privateKey = createPrivateKey(await readFile(keyFile));
    const publicDer = createPublicKey(privateKey).export({ type: 'spki', format: 'der' });
    if (!publicDer.equals(Buffer.from(CATALOG_PUBLIC_KEY_SPKI, 'base64'))) {
      throw new Error('Signing key does not match the pinned catalog public key.');
    }
    envelope = {
      schemaVersion: 1, algorithm: CATALOG_ALGORITHM, keyId: CATALOG_KEY_ID,
      signature: sign('sha256', catalogSigningPayload(catalog), {
        key: privateKey, dsaEncoding: 'ieee-p1363',
      }).toString('base64'),
    };
    await verifyCatalogSignature(catalog, envelope);
    await writeFile(signaturePath, JSON.stringify(envelope, null, 2) + '\n');
  } else {
    envelope = JSON.parse(await readFile(signaturePath, 'utf8'));
    await verifyCatalogSignature(catalog, envelope);
  }
  console.log(`CATALOG SIGNATURE ${mode === 'sign' ? 'SIGNED AND VERIFIED' : 'VERIFIED'}: ${directory}`);
} catch (error) {
  console.error(`CATALOG SIGNATURE FAILED: ${error.message}`);
  process.exitCode = 1;
}
