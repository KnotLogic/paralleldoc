const loader = require('../src/loader.js');
const assert = require('assert');

async function testJsLoader() {
  console.log('--- Starting comprehensive Node.js loader test suite ---');
  const enc = new TextEncoder();

  // 1. Exact raw SHA-256
  const text1 = '{"format": "paralleldoc", "version": "3.0"}';
  const bytes1 = enc.encode(text1);
  const hash1 = loader.computeRawSha256Sync(bytes1);
  assert.strictEqual(hash1.length, 64);
  assert.strictEqual(hash1, hash1.toLowerCase());
  console.log('Test 1: exact SHA-256 -> PASS');

  // 2. BOM preservation in hash
  const bomBytes = new Uint8Array([0xEF, 0xBB, 0xBF, ...bytes1]);
  const bomHash = loader.computeRawSha256Sync(bomBytes);
  assert.notStrictEqual(hash1, bomHash);
  console.log('Test 2: BOM alters hash -> PASS');

  // 3. CRLF vs LF divergence
  const lfBytes = enc.encode('{\n  "format": "paralleldoc"\n}');
  const crlfBytes = enc.encode('{\r\n  "format": "paralleldoc"\r\n}');
  assert.notStrictEqual(loader.computeRawSha256Sync(lfBytes), loader.computeRawSha256Sync(crlfBytes));
  console.log('Test 3: CRLF vs LF hash divergence -> PASS');

  // 4. Empty bytes
  const emptyRes = await loader.loadDocument(new Uint8Array([]));
  assert.strictEqual(emptyRes.success, false);
  assert.strictEqual(emptyRes.errorType, 'EMPTY_INPUT');
  assert.strictEqual(emptyRes.diagnosticMessage, loader.REJECTION_DIAGNOSTIC_MESSAGE);
  console.log('Test 4: Empty input rejection -> PASS');

  // 5. Legacy v2.1 rejection with exact diagnostic
  const legacyBytes = enc.encode(JSON.stringify({ metadata: {}, columns: [{ key: 'c1' }], items: [] }));
  const legacyRes = await loader.loadDocument(legacyBytes);
  assert.strictEqual(legacyRes.success, false);
  assert.strictEqual(legacyRes.errorType, 'REJECTED_UNSUPPORTED');
  assert.strictEqual(legacyRes.diagnosticMessage, '«Неподдерживаемый формат; требуется ParallelDoc 3.0»');
  assert.strictEqual(legacyRes.doc, null);
  console.log('Test 5: Legacy v2.1 rejection with exact diagnostic -> PASS');

  // 6. Non-v3 version rejection
  const wrongVerBytes = enc.encode(JSON.stringify({ format: 'paralleldoc', version: '2.1', metadata: {} }));
  const wrongVerRes = await loader.loadDocument(wrongVerBytes);
  assert.strictEqual(wrongVerRes.success, false);
  assert.strictEqual(wrongVerRes.errorType, 'REJECTED_UNSUPPORTED');
  assert.strictEqual(wrongVerRes.diagnosticMessage, '«Неподдерживаемый формат; требуется ParallelDoc 3.0»');
  console.log('Test 6: Wrong version rejection -> PASS');

  // 7. Syntax error tracking
  const badJsonBytes = enc.encode('{"format": "paralleldoc", "version": 3.0, trailing: }');
  const badJsonRes = await loader.loadDocument(badJsonBytes);
  assert.strictEqual(badJsonRes.success, false);
  assert.strictEqual(badJsonRes.errorType, 'PARSE_ERROR');
  assert(badJsonRes.rawPreview.snippet !== null);
  console.log('Test 7: Syntax error line/col tracking -> PASS');

  // 8. Truncation of large inputs (>5000 chars)
  const hugeText = '{"format": "invalid", "data": "' + 'A'.repeat(6000) + '"}';
  const hugeRes = await loader.loadDocument(enc.encode(hugeText));
  assert.strictEqual(hugeRes.rawPreview.isTruncated, true);
  assert(hugeRes.rawPreview.text.includes('Показаны первые'));
  console.log('Test 8: Safe preview truncation -> PASS');

  // 9. Valid document load
  const validDoc = {
    format: 'paralleldoc',
    version: '3.0',
    metadata: { document_id: 'doc-001', revision: 'rev-1', title: 'Test', author_refs: ['a1'] },
    authors: [{ id: 'a1', kind: 'human', name: 'Author' }],
    units: [], groups: [], visuals: [], assets: [], profiles: []
  };
  const validBytes = enc.encode(JSON.stringify(validDoc));
  const validRes = await loader.loadDocument(validBytes);
  assert.strictEqual(validRes.success, true);
  assert.strictEqual(validRes.structureState, 'valid');
  assert.strictEqual(validRes.integrityState, 'computed');
  console.log('Test 9: Valid document load -> PASS');

  // 10. Manifest matching scenarios
  const matchedManifest = {
    format: 'paralleldoc-integrity-1',
    algorithm: 'SHA-256',
    scope: 'raw-bytes',
    expected_sha256: validRes.rawSha256,
    document_id: 'doc-001',
    revision: 'rev-1'
  };
  const matchedRes = await loader.loadDocument(validBytes, matchedManifest);
  assert.strictEqual(matchedRes.integrityState, 'matched');
  assert.strictEqual(matchedRes.manifestResult.status, 'matched');

  const mismatchedManifest = Object.assign({}, matchedManifest, { expected_sha256: '0'.repeat(64) });
  const mismatchedRes = await loader.loadDocument(validBytes, mismatchedManifest);
  assert.strictEqual(mismatchedRes.integrityState, 'mismatch');
  assert.strictEqual(mismatchedRes.manifestResult.status, 'mismatch');

  const diffDocManifest = Object.assign({}, matchedManifest, { document_id: 'other-id' });
  const diffDocRes = await loader.loadDocument(validBytes, diffDocManifest);
  assert.strictEqual(diffDocRes.integrityState, 'computed');
  assert.strictEqual(diffDocRes.manifestResult.status, 'different_document');

  const invalidScopeManifest = Object.assign({}, matchedManifest, { scope: 'normalized-text' });
  const invalidScopeRes = await loader.loadDocument(validBytes, invalidScopeManifest);
  assert.strictEqual(invalidScopeRes.integrityState, 'computed');
  assert.strictEqual(invalidScopeRes.manifestResult.isValidManifest, false);
  console.log('Test 10: Manifest matching scenarios -> PASS');

  console.log('--- All Node.js loader tests PASSED successfully! ---');
}

testJsLoader().catch(err => {
  console.error(err);
  process.exit(1);
});
