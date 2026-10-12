import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { readFile, mkdtemp, rm, writeFile, cp } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createPublicKey, generateKeyPairSync, sign, verify } from 'node:crypto';
import { createPrivateKey } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { CATALOG_PUBLIC_KEY_SPKI, catalogSigningPayload, verifyCatalogSignature } from '../src/catalog-signature.js';

const catalogBytes = await readFile(new URL('../public/data/firmware-catalog.json', import.meta.url));
const signature = JSON.parse(await readFile(new URL('../public/data/firmware-catalog.sig.json', import.meta.url)));
let instance = 0;
async function freshCatalog(t, response) {
  const original = globalThis.document;
  globalThis.document = { baseURI: 'https://example.test/ape/' };
  t.after(() => {
    if (original === undefined) delete globalThis.document;
    else globalThis.document = original;
  });
  t.mock.method(globalThis, 'fetch', response);
  return import(`../src/catalog.js?signature-test=${instance++}`);
}

test('unsigned USB catalog is rejected before devices can be used', async t => {
  const requests = [];
  const { loadCatalog } = await freshCatalog(t, async (url, options) => {
    requests.push(new URL(url).pathname);
    assert.equal(options.cache, 'no-store');
    return new URL(url).pathname.endsWith('firmware-catalog.json')
      ? new Response(catalogBytes) : new Response('Not found', { status: 404 });
  });
  await assert.rejects(loadCatalog(), /signature/i);
  assert.ok(requests.every(path => path.startsWith('/ape/data/')));
});

test('the actual catalog signature verifies with WebCrypto and independent Node crypto', async () => {
  await verifyCatalogSignature(catalogBytes, signature);
  const key = createPublicKey({ key: Buffer.from(CATALOG_PUBLIC_KEY_SPKI, 'base64'), type: 'spki', format: 'der' });
  assert.equal(verify('sha256', catalogSigningPayload(catalogBytes),
    { key, dsaEncoding: 'ieee-p1363' }, Buffer.from(signature.signature, 'base64')), true);
});

test('a valid signed catalog is exposed only after verification and fetched once per session', async t => {
  const requests = [];
  const { loadCatalog } = await freshCatalog(t, async (url, options) => {
    assert.equal(options.cache, 'no-store');
    requests.push(new URL(url).pathname);
    return new Response(new URL(url).pathname.endsWith('firmware-catalog.json')
      ? catalogBytes : JSON.stringify(signature));
  });
  const [first, second] = await Promise.all([loadCatalog(), loadCatalog()]);
  assert.deepEqual(first, JSON.parse(catalogBytes));
  assert.equal(first, second);
  assert.deepEqual(requests.sort(), ['/ape/data/firmware-catalog.json', '/ape/data/firmware-catalog.sig.json']);
});

for (const [name, change] of [
  ['changed offsets and hashes', bytes => {
    const catalog = JSON.parse(bytes);
    catalog.devices[0].update.parts[0].offset = '0x0';
    catalog.devices[0].update.parts[0].sha256 = '0'.repeat(64);
    return Buffer.from(JSON.stringify(catalog));
  }],
  ['whitespace change', bytes => Buffer.concat([bytes, Buffer.from('\n')])],
]) {
  test(`${name} fails before firmware download`, async t => {
    const { loadCatalog } = await freshCatalog(t, async url => {
      assert.ok(new URL(url).pathname.startsWith('/ape/data/'));
      return new Response(new URL(url).pathname.endsWith('firmware-catalog.json')
        ? change(catalogBytes) : JSON.stringify(signature));
    });
    await assert.rejects(loadCatalog(), /signature verification failed/);
  });
}

for (const [name, change] of [
  ['wrong key ID', s => { s.keyId = 'attacker'; }],
  ['wrong algorithm', s => { s.algorithm = 'none'; }],
  ['wrong schema', s => { s.schemaVersion = 2; }],
  ['untrusted public key', s => { s.publicKey = CATALOG_PUBLIC_KEY_SPKI; }],
  ['corrupt signature', s => { s.signature = Buffer.alloc(64).toString('base64'); }],
  ['short signature', s => { s.signature = Buffer.alloc(10).toString('base64'); }],
  ['non-base64 signature', s => { s.signature = '<bad>'; }],
  ['missing signature', s => { delete s.signature; }],
]) {
  test(`rejects ${name}`, async () => {
    const envelope = structuredClone(signature);
    change(envelope);
    await assert.rejects(verifyCatalogSignature(catalogBytes, envelope), /signature/i);
  });
}

test('re-signing with an attacker P-256 key cannot replace the pinned key', async () => {
  const { privateKey } = generateKeyPairSync('ec', { namedCurve: 'prime256v1' });
  const forged = { ...signature, signature: sign('sha256', catalogSigningPayload(catalogBytes),
    { key: privateKey, dsaEncoding: 'ieee-p1363' }).toString('base64') };
  await assert.rejects(verifyCatalogSignature(catalogBytes, forged), /signature verification failed/);
});

test('a failed signature fetch can retry without an unsigned fallback', async t => {
  let available = false;
  const { loadCatalog } = await freshCatalog(t, async url => {
    if (new URL(url).pathname.endsWith('firmware-catalog.json')) return new Response(catalogBytes);
    return available ? new Response(JSON.stringify(signature)) : new Response('missing', { status: 404 });
  });
  await assert.rejects(loadCatalog(), /signature/);
  available = true;
  assert.deepEqual(await loadCatalog(), JSON.parse(catalogBytes));
});

test('a crypto failure never falls back to unsigned data', async t => {
  t.mock.method(globalThis.crypto.subtle, 'verify', async () => { throw Error('crypto unavailable'); });
  await assert.rejects(verifyCatalogSignature(catalogBytes, signature), /crypto unavailable/);
});

// Run the real CLI in a throwaway directory so a bug can never rewrite the
// repository's committed signature.
const cli = new URL('../scripts/catalog-signature.mjs', import.meta.url).pathname;
let publicCopy;
let digest;
let committed;
const runCli = args => {
  const result = spawnSync(process.execPath, [cli, ...args], { encoding: 'utf8' });
  return { status: result.status, stderr: result.stderr.trim(), stdout: result.stdout.trim() };
};
await (async () => {
  // Copy first, then register cleanup, so no remover can race the copy.
  publicCopy = await mkdtemp(join(tmpdir(), 'ape-catalog-cli-'));
  try {
    await cp(new URL('../public', import.meta.url), publicCopy, { recursive: true });
  } catch (error) {
    await rm(publicCopy, { recursive: true, force: true });
    throw error;
  }
  after(() => rm(publicCopy, { recursive: true, force: true }));
  digest = bytes => createHash('sha256').update(bytes).digest('hex');
  committed = await readFile(new URL('../public/data/firmware-catalog.sig.json', import.meta.url));
})();
for (const [name, args] of [
  ['no mode', []],
  ['unknown mode', ['touch', publicCopy]],
  ['verify with a key argument', ['verify', publicCopy, '/tmp/key.pem']],
  ['sign without a key', ['sign', publicCopy]],
  ['extra arguments', ['verify', publicCopy, 'x', 'y']],
  ['missing directory', ['verify', join(publicCopy, 'nope')]],
  ['public key passed as private key', ['sign', publicCopy,
    new URL('../public/firmware/heltec-v4/ota-public-key.pem', import.meta.url).pathname]],
  ['missing key file', ['sign', publicCopy, join(publicCopy, 'absent.pem')]],
]) {
  test(`CLI rejects: ${name}`, () => {
    const run = runCli(args);
    assert.equal(run.status, 1, `${name} must fail`);
    assert.match(run.stderr, /CATALOG SIGNATURE FAILED/);
    assert.equal(run.stdout, '');
  });
}

test('a failing CLI never modifies the committed catalog signature', async () => {
  assert.equal(digest(await readFile(new URL('../public/data/firmware-catalog.sig.json', import.meta.url))), digest(committed));
  assert.equal(runCli(['verify', publicCopy]).status, 0);
  assert.equal(runCli(['verify', publicCopy]).status, 0);
});

test('the CLI refuses a valid P-256 private key that is not the pinned one', async () => {
  const { privateKey } = generateKeyPairSync('ec', { namedCurve: 'prime256v1' });
  const foreign = join(publicCopy, 'foreign.pem');
  await writeFile(foreign, privateKey.export({ type: 'pkcs8', format: 'pem' }));
  const before = digest(await readFile(join(publicCopy, 'data/firmware-catalog.sig.json')));
  const run = runCli(['sign', publicCopy, foreign]);
  assert.equal(run.status, 1);
  assert.match(run.stderr, /does not match the pinned catalog public key/);
  assert.equal(digest(await readFile(join(publicCopy, 'data/firmware-catalog.sig.json'))), before);
  assert.ok(createPrivateKey(await readFile(foreign)));
});
