/**
 * Adversarial Stress Test Suite for ParallelDoc 3.0 Node.js / Browser Loader.
 * Focus: Pure JS SHA-256 vs WebCrypto vs Node Crypto, BOM boundaries, mixed line endings,
 * non-UTF8 bytes, 0-byte input, multi-megabyte payloads, and byte immutability.
 */

const assert = require('assert');
const crypto = require('crypto');
const loader = require('../src/loader.js');

function nodeSha256(buf) {
  return crypto.createHash('sha256').update(buf).digest('hex');
}

function getMinimalValidDoc() {
  return {
    format: 'paralleldoc',
    version: '3.0',
    metadata: {
      document_id: 'doc-adv-js',
      revision: 'r1',
      title: 'JS Adversarial Test Doc',
      author_refs: ['auth-1']
    },
    authors: [{ id: 'auth-1', kind: 'human', name: 'JS Adversary' }],
    units: [],
    groups: [],
    visuals: [],
    assets: [],
    profiles: []
  };
}

async function runAdversarialNodeTests() {
  console.log('=== Starting ParallelDoc Loader Adversarial Node.js Tests ===');

  // ===========================================================================
  // 1. Byte Immutability Tests
  // ===========================================================================
  console.log('\n[1] Testing Byte Immutability & Non-Mutation...');
  {
    const original = Buffer.from('{\r\n  "format": "paralleldoc",\r\n  "version": "3.0"\r\n}');
    const copy = Buffer.from(original);
    const u8 = new Uint8Array(original);
    const u8Copy = new Uint8Array(copy);

    const hashSync = loader.sha256Pure(u8);
    assert.deepStrictEqual(u8, u8Copy, 'sha256Pure mutated input Uint8Array!');
    assert.strictEqual(hashSync, nodeSha256(copy));

    const hashAsync = await loader.computeRawSha256(u8);
    assert.deepStrictEqual(u8, u8Copy, 'computeRawSha256 mutated input Uint8Array!');
    assert.strictEqual(hashAsync, nodeSha256(copy));

    const loadRes = await loader.loadDocument(u8);
    assert.deepStrictEqual(u8, u8Copy, 'loadDocument mutated input Uint8Array!');
    console.log('  -> Byte immutability verified: PASS');
  }

  // ===========================================================================
  // 2. Line Ending Sensitivity & Zero-Normalization
  // ===========================================================================
  console.log('\n[2] Testing Line Ending Sensitivity & Zero-Normalization...');
  {
    const baseJson = '{"format":"paralleldoc","version":"3.0","document_id":"test"}';
    const lf = Buffer.from(baseJson.replace(/,/g, ',\n'), 'utf-8');
    const crlf = Buffer.from(baseJson.replace(/,/g, ',\r\n'), 'utf-8');
    const cr = Buffer.from(baseJson.replace(/,/g, ',\r'), 'utf-8');
    const mixed = Buffer.from(baseJson.replace(/,/, ',\r\n').replace(/3\.0"/, '3.0"\n'), 'utf-8');

    const hashes = {
      lf: loader.sha256Pure(new Uint8Array(lf)),
      crlf: loader.sha256Pure(new Uint8Array(crlf)),
      cr: loader.sha256Pure(new Uint8Array(cr)),
      mixed: loader.sha256Pure(new Uint8Array(mixed))
    };

    // All must match Node crypto
    assert.strictEqual(hashes.lf, nodeSha256(lf));
    assert.strictEqual(hashes.crlf, nodeSha256(crlf));
    assert.strictEqual(hashes.cr, nodeSha256(cr));
    assert.strictEqual(hashes.mixed, nodeSha256(mixed));

    // All must be mutually distinct (no normalization)
    const uniqueHashes = new Set(Object.values(hashes));
    assert.strictEqual(uniqueHashes.size, 4, 'Line endings were normalized during hashing!');
    console.log('  -> Distinct hashes for LF, CRLF, CR, Mixed: PASS');
  }

  // ===========================================================================
  // 3. Partial BOM & BOM Boundaries
  // ===========================================================================
  console.log('\n[3] Testing Partial BOM & BOM Boundaries...');
  {
    const doc = getMinimalValidDoc();
    const docJson = Buffer.from(JSON.stringify(doc), 'utf-8');

    // Partial BOM: \xEF\xBB without \xBF
    const partial2 = Buffer.concat([Buffer.from([0xEF, 0xBB]), docJson]);
    const u8Partial2 = new Uint8Array(partial2);
    const hashPartial2 = loader.sha256Pure(u8Partial2);
    assert.strictEqual(hashPartial2, nodeSha256(partial2));

    const resPartial2 = await loader.loadDocument(u8Partial2);
    assert.strictEqual(resPartial2.rawSha256, hashPartial2);
    assert.strictEqual(resPartial2.hasBom, false, 'Partial BOM must NOT report hasBom=true');
    assert.strictEqual(resPartial2.success, false);
    assert.strictEqual(resPartial2.errorType, 'UTF8_DECODE_ERROR');
    console.log('  -> Partial BOM (2 bytes) rejection: PASS');

    // Partial BOM: \xEF alone (1 byte)
    const partial1 = Buffer.concat([Buffer.from([0xEF]), docJson]);
    const resPartial1 = await loader.loadDocument(new Uint8Array(partial1));
    assert.strictEqual(resPartial1.hasBom, false);
    assert.strictEqual(resPartial1.errorType, 'UTF8_DECODE_ERROR');
    console.log('  -> Partial BOM (1 byte) rejection: PASS');

    // Double BOM: \xEF\xBB\xBF\xEF\xBB\xBF + json
    const doubleBom = Buffer.concat([Buffer.from([0xEF, 0xBB, 0xBF, 0xEF, 0xBB, 0xBF]), docJson]);
    const u8DoubleBom = new Uint8Array(doubleBom);
    const hashDouble = loader.sha256Pure(u8DoubleBom);
    const resDouble = await loader.loadDocument(u8DoubleBom);
    assert.strictEqual(resDouble.rawSha256, hashDouble);
    assert.strictEqual(resDouble.hasBom, true);
    // Note: Python loader rejects Double BOM as PARSE_ERROR because Python's utf-8 decode
    // leaves the second BOM as \uFEFF which is invalid JSON syntax.
    // In JS loader, decodeJsonText strips the 1st BOM via subarray(3), and then TextDecoder
    // (with default ignoreBOM: false) strips the 2nd BOM, leading to an asymmetry!
    console.log(`  -> Double BOM in JS loader: success=${resDouble.success} (Asymmetry note: JS TextDecoder strips 2nd BOM, Python rejects)`);

    // Exact BOM alone (3 bytes)
    const bomAlone = new Uint8Array([0xEF, 0xBB, 0xBF]);
    const resBomAlone = await loader.loadDocument(bomAlone);
    assert.strictEqual(resBomAlone.hasBom, true);
    assert.strictEqual(resBomAlone.rawSha256, nodeSha256(Buffer.from([0xEF, 0xBB, 0xBF])));
    assert.strictEqual(resBomAlone.success, false);
    console.log('  -> Exact BOM alone handled cleanly: PASS');
  }

  // ===========================================================================
  // 4. Non-UTF-8 Sequences
  // ===========================================================================
  console.log('\n[4] Testing Non-UTF-8 Sequences...');
  {
    // High byte 0xFF
    const bad1 = Buffer.concat([Buffer.from('{"format":"paralleldoc","version":"3.0","bad":"'), Buffer.from([0xFF, 0xFE]), Buffer.from('"}')]);
    const u8Bad1 = new Uint8Array(bad1);
    const hashBad1 = loader.sha256Pure(u8Bad1);
    assert.strictEqual(hashBad1, nodeSha256(bad1));

    const resBad1 = await loader.loadDocument(u8Bad1);
    assert.strictEqual(resBad1.rawSha256, hashBad1);
    assert.strictEqual(resBad1.success, false);
    assert.strictEqual(resBad1.errorType, 'UTF8_DECODE_ERROR');
    console.log('  -> 0xFF/0xFE invalid bytes handled cleanly: PASS');

    // Overlong null: 0xC0 0x80
    const badOverlong = Buffer.from([0x7B, 0x22, 0x61, 0x22, 0x3A, 0x22, 0xC0, 0x80, 0x22, 0x7D]);
    const resOverlong = await loader.loadDocument(new Uint8Array(badOverlong));
    assert.strictEqual(resOverlong.success, false);
    assert.strictEqual(resOverlong.errorType, 'UTF8_DECODE_ERROR');
    console.log('  -> Overlong null sequence handled cleanly: PASS');
  }

  // ===========================================================================
  // 5. 0-Byte Input Handling
  // ===========================================================================
  console.log('\n[5] Testing 0-Byte Input...');
  {
    const emptyU8 = new Uint8Array(0);
    const expectedEmptyHash = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855';

    assert.strictEqual(loader.sha256Pure(emptyU8), expectedEmptyHash);
    assert.strictEqual(await loader.computeRawSha256(emptyU8), expectedEmptyHash);

    const resEmpty = await loader.loadDocument(emptyU8);
    assert.strictEqual(resEmpty.rawSha256, expectedEmptyHash);
    assert.strictEqual(resEmpty.byteLength, 0);
    assert.strictEqual(resEmpty.hasBom, false);
    assert.strictEqual(resEmpty.success, false);
    assert.strictEqual(resEmpty.errorType, 'EMPTY_INPUT');
    assert.strictEqual(resEmpty.diagnosticMessage, loader.REJECTION_DIAGNOSTIC_MESSAGE);
    console.log('  -> 0-byte input rejection: PASS');
  }

  // ===========================================================================
  // 6. Subarray with Non-Zero byteOffset Stress
  // ===========================================================================
  console.log('\n[6] Testing Subarray with Non-Zero byteOffset...');
  {
    const backingBuffer = new ArrayBuffer(100);
    const u8Full = new Uint8Array(backingBuffer);
    for (let i = 0; i < 100; i++) u8Full[i] = i;

    // Subarray from index 10 to 30 (20 bytes)
    const sub = u8Full.subarray(10, 30);
    assert.strictEqual(sub.byteOffset, 10);
    assert.strictEqual(sub.length, 20);

    const expectedSubHash = nodeSha256(Buffer.from(backingBuffer, 10, 20));

    const pureHash = loader.sha256Pure(sub);
    assert.strictEqual(pureHash, expectedSubHash, 'sha256Pure failed on subarray with byteOffset > 0!');

    const asyncHash = await loader.computeRawSha256(sub);
    assert.strictEqual(asyncHash, expectedSubHash, 'computeRawSha256 failed on subarray with byteOffset > 0!');
    console.log('  -> Subarray non-zero byteOffset hashing: PASS');
  }

  // ===========================================================================
  // 7. Multi-Megabyte Stress Tests (1MB, 5MB, 10MB)
  // ===========================================================================
  console.log('\n[7] Testing Multi-Megabyte Payloads...');
  {
    // 1 MB payload
    const size1MB = 1024 * 1024;
    const buf1MB = Buffer.alloc(size1MB);
    for (let i = 0; i < size1MB; i++) buf1MB[i] = (i * 31) & 0xFF;
    const u8_1MB = new Uint8Array(buf1MB);

    const exp1MB = nodeSha256(buf1MB);

    const t0 = Date.now();
    const hash1MB_pure = loader.sha256Pure(u8_1MB);
    const dt_pure = Date.now() - t0;
    assert.strictEqual(hash1MB_pure, exp1MB);

    const hash1MB_async = await loader.computeRawSha256(u8_1MB);
    assert.strictEqual(hash1MB_async, exp1MB);
    console.log(`  -> 1MB hash verified (pure: ${dt_pure}ms): PASS`);

    // 5 MB payload
    const size5MB = 5 * 1024 * 1024;
    const buf5MB = Buffer.alloc(size5MB);
    for (let i = 0; i < size5MB; i++) buf5MB[i] = (i * 17) & 0xFF;
    const u8_5MB = new Uint8Array(buf5MB);

    const exp5MB = nodeSha256(buf5MB);
    const hash5MB_pure = loader.sha256Pure(u8_5MB);
    assert.strictEqual(hash5MB_pure, exp5MB);

    const hash5MB_async = await loader.computeRawSha256(u8_5MB);
    assert.strictEqual(hash5MB_async, exp5MB);
    console.log('  -> 5MB hash verified: PASS');

    // 10 MB payload
    const size10MB = 10 * 1024 * 1024;
    const buf10MB = Buffer.alloc(size10MB);
    for (let i = 0; i < size10MB; i++) buf10MB[i] = (i * 7) & 0xFF;
    const u8_10MB = new Uint8Array(buf10MB);

    const exp10MB = nodeSha256(buf10MB);
    const hash10MB_async = await loader.computeRawSha256(u8_10MB);
    assert.strictEqual(hash10MB_async, exp10MB);
    console.log('  -> 10MB hash verified: PASS');
  }

  // ===========================================================================
  // 8. Rejection View DOM Security Sanity Check (AC-42)
  // ===========================================================================
  console.log('\n[8] Testing Safe Raw Preview & Rejection View Contract...');
  {
    const payload = Buffer.from('{\n  "metadata": {"title": "<script>alert(1)</script>"},\n  "columns": []\n}', 'utf-8');
    const res = await loader.loadDocument(new Uint8Array(payload));

    assert.strictEqual(res.success, false);
    assert.strictEqual(res.errorType, 'REJECTED_UNSUPPORTED');
    assert.strictEqual(res.diagnosticMessage, loader.REJECTION_DIAGNOSTIC_MESSAGE);
    assert.ok(res.rawPreview, 'rawPreview must be generated');
    assert.ok(res.rawPreview.text.includes('<script>alert(1)</script>'));
    assert.ok(res.rawPreview.snippet.includes('columns'));
    console.log('  -> Safe raw preview and rejection diagnostics: PASS');
  }

  console.log('\n=== All ParallelDoc Loader Adversarial Node.js Tests PASSED successfully! ===');
}

runAdversarialNodeTests().catch(err => {
  console.error('\n❌ Adversarial Node.js test failed with error:', err);
  process.exit(1);
});
