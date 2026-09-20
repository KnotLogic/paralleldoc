/**
 * ParallelDoc 3.0 (r2 / V3-ONLY) — Adversarial Stress Test Suite for Node.js / JS Loader.
 * Author: Challenger M2-2 (Adversarial Stress on Format Guard & Manifest)
 */

const loader = require('../src/loader.js');
const assert = require('assert');

async function runAdversarialJsTests() {
  console.log('=== Starting Adversarial Stress Test Suite for JS Loader ===');
  const enc = new TextEncoder();
  let passed = 0;
  let failed = 0;
  const discrepancies = [];

  function check(name, fn) {
    try {
      fn();
      passed++;
      // console.log(`  [PASS] ${name}`);
    } catch (err) {
      failed++;
      console.log(`  [FAIL] ${name}: ${err.message}`);
      discrepancies.push({ test: name, error: err.message });
    }
  }

  async function checkAsync(name, fn) {
    try {
      await fn();
      passed++;
      // console.log(`  [PASS] ${name}`);
    } catch (err) {
      failed++;
      console.log(`  [FAIL] ${name}: ${err.message}`);
      discrepancies.push({ test: name, error: err.message });
    }
  }

  // --------------------------------------------------------------------------
  // 1. NON-DICT ROOT TYPES
  // --------------------------------------------------------------------------
  console.log('\n--- 1. Testing Non-Dict Root Types ---');
  const nonDictInputs = [
    { label: 'empty array', input: '[]' },
    { label: 'number array', input: '[1, 2, 3]' },
    { label: 'array with v3 tokens', input: '["paralleldoc", "3.0"]' },
    { label: 'array of v3 doc', input: '[{"format": "paralleldoc", "version": "3.0"}]' },
    { label: 'boolean true', input: 'true' },
    { label: 'boolean false', input: 'false' },
    { label: 'null value', input: 'null' },
    { label: 'number 0', input: '0' },
    { label: 'number 42', input: '42' },
    { label: 'negative number', input: '-99' },
    { label: 'float number', input: '3.14159' },
    { label: 'string', input: '"paralleldoc"' }
  ];

  for (const item of nonDictInputs) {
    await checkAsync(`Non-dict root: ${item.label}`, async () => {
      const res = await loader.loadDocument(enc.encode(item.input));
      assert.strictEqual(res.success, false, 'success must be false');
      assert.strictEqual(res.errorType, 'REJECTED_UNSUPPORTED', 'errorType must be REJECTED_UNSUPPORTED');
      assert.strictEqual(res.diagnosticMessage, loader.REJECTION_DIAGNOSTIC_MESSAGE, 'must match exact diagnostic message');
      assert.strictEqual(res.doc, null, 'doc must be null');
      assert.strictEqual(res.structureState, 'invalid', 'structureState must be invalid');
      assert.strictEqual(res.integrityState, 'computed', 'integrityState must be computed');
    });
  }

  // --------------------------------------------------------------------------
  // 2. SPOOFED V3 WITH LEGACY KEYS
  // --------------------------------------------------------------------------
  console.log('\n--- 2. Testing Spoofed V3 Files with Legacy Keys ---');
  const legacyVariations = [
    { key: 'columns', val: [] },
    { key: 'columns', val: [{ key: 'c1' }] },
    { key: 'columns', val: null },
    { key: 'columns', val: 'legacy' },
    { key: 'columns', val: {} },
    { key: 'items', val: [] },
    { key: 'items', val: [{ id: '1' }] },
    { key: 'items', val: null },
    { key: 'items', val: 'legacy' }
  ];

  for (const v of legacyVariations) {
    await checkAsync(`Spoofed v3 with legacy root key: ${v.key} = ${JSON.stringify(v.val)}`, async () => {
      const doc = {
        format: 'paralleldoc',
        version: '3.0',
        metadata: { document_id: 'd1', revision: 'r1', title: 'T' },
        authors: [], units: [], groups: [], visuals: [], assets: [], profiles: []
      };
      doc[v.key] = v.val;
      const res = await loader.loadDocument(enc.encode(JSON.stringify(doc)));
      assert.strictEqual(res.success, false);
      assert.strictEqual(res.errorType, 'REJECTED_UNSUPPORTED');
      assert.strictEqual(res.diagnosticMessage, loader.REJECTION_DIAGNOSTIC_MESSAGE);
      assert.strictEqual(res.doc, null);
    });
  }

  // Substrings of legacy keys inside strings MUST NOT be rejected
  await checkAsync('Valid v3 with "columns" and "items" words inside string values', async () => {
    const doc = {
      format: 'paralleldoc',
      version: '3.0',
      metadata: { document_id: 'd1', revision: 'r1', title: 'Discussion of "columns": [] and "items": []' },
      authors: [], units: [], groups: [], visuals: [], assets: [], profiles: []
    };
    const res = await loader.loadDocument(enc.encode(JSON.stringify(doc)));
    assert.strictEqual(res.success, true);
    assert.strictEqual(res.errorType, 'NONE');
    assert(res.doc !== null);
  });

  // --------------------------------------------------------------------------
  // 3. SYNTAX STRESS & LINE/COL LOCATOR
  // --------------------------------------------------------------------------
  console.log('\n--- 3. Testing Corrupted JSON Syntax & Locator ---');

  await checkAsync('Nested syntax error line/col tracking', async () => {
    const corrupted = '{\n  "format": "paralleldoc",\n  "version": "3.0",\n  "metadata": {\n    "level": {\n      "bad": [1, 2, UNQUOTED_TOKEN]\n    }\n  }\n}';
    const res = await loader.loadDocument(enc.encode(corrupted));
    assert.strictEqual(res.success, false);
    assert.strictEqual(res.errorType, 'PARSE_ERROR');
    assert(res.line >= 5, `Expected line >= 5, got ${res.line}`);
    assert(res.snippet && res.snippet.includes('^'), 'Caret snippet must be present');
  });

  await checkAsync('Unclosed string literal', async () => {
    const unclosed = '{\n  "format": "paralleldoc",\n  "title": "unclosed\n}';
    const res = await loader.loadDocument(enc.encode(unclosed));
    assert.strictEqual(res.success, false);
    assert.strictEqual(res.errorType, 'PARSE_ERROR');
  });

  // --------------------------------------------------------------------------
  // 4. MALFORMED DETACHED MANIFESTS
  // --------------------------------------------------------------------------
  console.log('\n--- 4. Testing Malformed Detached Manifests ---');

  const validDocBytes = enc.encode(JSON.stringify({
    format: 'paralleldoc',
    version: '3.0',
    metadata: { document_id: 'doc-001', revision: 'rev-1' },
    authors: [], units: [], groups: [], visuals: [], assets: [], profiles: []
  }));
  const validHash = loader.computeRawSha256Sync(validDocBytes);

  // Wrong algorithm
  check('Reject manifest with algorithm: "SHA-512"', () => {
    const man = { format: 'paralleldoc-integrity-1', algorithm: 'SHA-512', scope: 'raw-bytes', expected_sha256: validHash };
    const res = loader.verifyManifest(validDocBytes, man);
    assert.strictEqual(res.isValidManifest, false);
    assert.strictEqual(res.status, 'invalid_manifest');
  });

  check('Reject manifest with lowercase algorithm: "sha-256"', () => {
    const man = { format: 'paralleldoc-integrity-1', algorithm: 'sha-256', scope: 'raw-bytes', expected_sha256: validHash };
    const res = loader.verifyManifest(validDocBytes, man);
    assert.strictEqual(res.isValidManifest, false);
    assert.strictEqual(res.status, 'invalid_manifest');
  });

  // Wrong scope
  check('Reject manifest with scope: "normalized-text"', () => {
    const man = { format: 'paralleldoc-integrity-1', algorithm: 'SHA-256', scope: 'normalized-text', expected_sha256: validHash };
    const res = loader.verifyManifest(validDocBytes, man);
    assert.strictEqual(res.isValidManifest, false);
    assert.strictEqual(res.status, 'invalid_manifest');
  });

  check('Reject manifest with scope: "raw_bytes" (underscore)', () => {
    const man = { format: 'paralleldoc-integrity-1', algorithm: 'SHA-256', scope: 'raw_bytes', expected_sha256: validHash };
    const res = loader.verifyManifest(validDocBytes, man);
    assert.strictEqual(res.isValidManifest, false);
    assert.strictEqual(res.status, 'invalid_manifest');
  });

  // Wrong format
  check('Reject manifest with format: "paralleldoc"', () => {
    const man = { format: 'paralleldoc', algorithm: 'SHA-256', scope: 'raw-bytes', expected_sha256: validHash };
    const res = loader.verifyManifest(validDocBytes, man);
    assert.strictEqual(res.isValidManifest, false);
    assert.strictEqual(res.status, 'invalid_manifest');
  });

  // Uppercase hex: Spec §8 line 446 requires pattern: ^[a-f0-9]{64}$ (lowercase)
  check('Manifest with uppercase hex expected_sha256 (Schema compliance: lowercase only)', () => {
    const upperHash = validHash.toUpperCase();
    const man = { format: 'paralleldoc-integrity-1', algorithm: 'SHA-256', scope: 'raw-bytes', expected_sha256: upperHash };
    const res = loader.verifyManifest(validDocBytes, man);
    // Note: manifest.schema.json has "pattern": "^[a-f0-9]{64}$" which strictly rejects uppercase!
    assert.strictEqual(res.isValidManifest, false, 'Uppercase hex violates manifest.schema.json ^[a-f0-9]{64}$');
    assert.strictEqual(res.status, 'invalid_manifest');
  });

  // Extra properties: manifest.schema.json has additionalProperties: false
  check('Manifest with extra properties (Schema compliance: additionalProperties: false)', () => {
    const man = {
      format: 'paralleldoc-integrity-1',
      algorithm: 'SHA-256',
      scope: 'raw-bytes',
      expected_sha256: validHash,
      signature: 'unauthorized_sig',
      injected_field: 123
    };
    const res = loader.verifyManifest(validDocBytes, man);
    assert.strictEqual(res.isValidManifest, false, 'Extra properties violate manifest.schema.json additionalProperties: false');
    assert.strictEqual(res.status, 'invalid_manifest');
  });

  // Malformed expected_sha256 lengths & characters
  const badHashes = [
    { h: validHash.slice(0, 63), desc: '63 chars' },
    { h: validHash + 'a', desc: '65 chars' },
    { h: 'g'.repeat(64), desc: 'non-hex character g' },
    { h: '0x' + validHash.slice(2), desc: '0x prefix' }
  ];
  for (const bh of badHashes) {
    check(`Reject malformed hash: ${bh.desc}`, () => {
      const man = { format: 'paralleldoc-integrity-1', algorithm: 'SHA-256', scope: 'raw-bytes', expected_sha256: bh.h };
      const res = loader.verifyManifest(validDocBytes, man);
      assert.strictEqual(res.isValidManifest, false);
      assert.strictEqual(res.status, 'invalid_manifest');
    });
  }

  // --------------------------------------------------------------------------
  // 5. TARGET BINDING & MULTI-ERROR
  // --------------------------------------------------------------------------
  console.log('\n--- 5. Testing Target Binding & Multi-Errors ---');

  check('Manifest target binding takes precedence over hash mismatch', () => {
    const man = {
      format: 'paralleldoc-integrity-1',
      algorithm: 'SHA-256',
      scope: 'raw-bytes',
      expected_sha256: '0'.repeat(64), // Mismatched hash
      document_id: 'different-doc-id'
    };
    const res = loader.verifyManifest(validDocBytes, man, { document_id: 'doc-001' });
    assert.strictEqual(res.isValidManifest, true);
    assert.strictEqual(res.status, 'different_document');
  });

  await checkAsync('Simultaneous schema error and hash mismatch', async () => {
    // Missing required collection 'authors'
    const brokenDoc = {
      format: 'paralleldoc',
      version: '3.0',
      metadata: { document_id: 'doc-broken' },
      units: [], groups: [], visuals: [], assets: [], profiles: []
    };
    const brokenBytes = enc.encode(JSON.stringify(brokenDoc));
    const man = {
      format: 'paralleldoc-integrity-1',
      algorithm: 'SHA-256',
      scope: 'raw-bytes',
      expected_sha256: '0'.repeat(64),
      document_id: 'doc-broken'
    };
    const res = await loader.loadDocument(brokenBytes, man);
    assert.strictEqual(res.structureState, 'invalid');
    assert.strictEqual(res.integrityState, 'mismatch');
    assert.strictEqual(res.manifestResult.status, 'mismatch');
  });

  // --------------------------------------------------------------------------
  // 6. ZERO AUTO-MIGRATION & ZERO SILENT FALLBACK
  // --------------------------------------------------------------------------
  console.log('\n--- 6. Testing Zero Auto-Migration & Silent Fallback ---');

  await checkAsync('Legacy v2.1 document is strictly rejected with null doc', async () => {
    const legacy = {
      metadata: { title: 'Legacy' },
      columns: [{ key: 'c1' }, { key: 'c2' }, { key: 'c3' }],
      items: [{ id: '1', c1: 'text', c2: 'trans', c3: 'risk' }]
    };
    const res = await loader.loadDocument(enc.encode(JSON.stringify(legacy)));
    assert.strictEqual(res.success, false);
    assert.strictEqual(res.doc, null);
    assert.strictEqual(res.stats.units_count || 0, 0);
  });

  console.log('\n=== Adversarial Stress Test Suite Finished ===');
  console.log(`Passed: ${passed}, Failed: ${failed}`);
  if (discrepancies.length > 0) {
    console.log('\n=== DISCREPANCIES / FAILURES DETECTED ===');
    for (const d of discrepancies) {
      console.log(`- ${d.test}: ${d.error}`);
    }
  }

  return { passed, failed, discrepancies };
}

runAdversarialJsTests().then(res => {
  if (res.failed > 0) {
    console.log('\nExiting with status code 0 to allow challenger analysis (discrepancies recorded).');
  }
}).catch(err => {
  console.error('Fatal runner crash:', err);
  process.exit(1);
});
