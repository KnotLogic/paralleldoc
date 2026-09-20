/**
 * ParallelDoc 3.0 (r2 / V3-ONLY) — Challenger M2-r2 Adversarial Verification Suite.
 *
 * Empirical verification of all 3 remediated findings:
 * 1. Lowercase-only hex enforcement in manifest `expected_sha256` (^[a-f0-9]{64}$).
 * 2. Strict rejection of undeclared properties (additionalProperties: false) & non-string document_id/revision.
 * 3. V8 syntax error line/column locator fallback under complex and deceptive JSON syntax errors.
 */

const loader = require('../src/loader.js');
const assert = require('assert');

async function runChallengerM2R2Stress() {
  console.log('=== Starting Challenger M2-r2 Extended Adversarial Stress Suite ===\n');
  const enc = new TextEncoder();
  let passed = 0;
  let failed = 0;
  const failures = [];

  function test(name, fn) {
    try {
      fn();
      passed++;
      // console.log(`  [PASS] ${name}`);
    } catch (err) {
      failed++;
      console.error(`  [FAIL] ${name}: ${err.message}`);
      failures.push({ name, error: err.message });
    }
  }

  async function testAsync(name, fn) {
    try {
      await fn();
      passed++;
      // console.log(`  [PASS] ${name}`);
    } catch (err) {
      failed++;
      console.error(`  [FAIL] ${name}: ${err.message}`);
      failures.push({ name, error: err.message });
    }
  }

  const validDoc = {
    format: 'paralleldoc',
    version: '3.0',
    metadata: {
      document_id: 'doc-alpha',
      revision: 'rev-1',
      title: 'Valid V3 Doc',
      author_refs: ['auth-1'],
      created_at: '2026-09-06T12:00:00Z'
    },
    authors: [{ id: 'auth-1', name: 'Author One', kind: 'human' }],
    units: [],
    groups: [],
    visuals: [],
    assets: [],
    profiles: []
  };
  const validDocBytes = enc.encode(JSON.stringify(validDoc));
  const validHash = loader.computeRawSha256Sync(validDocBytes);

  // ==========================================================================
  // DISCREPANCY 1: STRICT LOWERCASE HEX SHA-256 ENFORCEMENT
  // ==========================================================================
  console.log('--- Area 1: Manifest expected_sha256 Lowercase Hex Enforcement ---');

  test('Valid lowercase 64-char hex hash passes', () => {
    const man = {
      format: 'paralleldoc-integrity-1',
      algorithm: 'SHA-256',
      scope: 'raw-bytes',
      expected_sha256: validHash
    };
    const res = loader.verifyManifest(validDocBytes, man);
    assert.strictEqual(res.isValidManifest, true);
    assert.strictEqual(res.status, 'matched');
  });

  test('Reject entirely uppercase 64-char hex hash', () => {
    const man = {
      format: 'paralleldoc-integrity-1',
      algorithm: 'SHA-256',
      scope: 'raw-bytes',
      expected_sha256: validHash.toUpperCase()
    };
    const res = loader.verifyManifest(validDocBytes, man);
    assert.strictEqual(res.isValidManifest, false);
    assert.strictEqual(res.status, 'invalid_manifest');
  });

  test('Reject first character uppercase', () => {
    const upperFirst = validHash[0].toUpperCase() + validHash.slice(1);
    if (upperFirst !== validHash) {
      const man = {
        format: 'paralleldoc-integrity-1',
        algorithm: 'SHA-256',
        scope: 'raw-bytes',
        expected_sha256: upperFirst
      };
      const res = loader.verifyManifest(validDocBytes, man);
      assert.strictEqual(res.isValidManifest, false);
      assert.strictEqual(res.status, 'invalid_manifest');
    }
  });

  test('Reject last character uppercase', () => {
    const upperLast = validHash.slice(0, 63) + validHash[63].toUpperCase();
    if (upperLast !== validHash) {
      const man = {
        format: 'paralleldoc-integrity-1',
        algorithm: 'SHA-256',
        scope: 'raw-bytes',
        expected_sha256: upperLast
      };
      const res = loader.verifyManifest(validDocBytes, man);
      assert.strictEqual(res.isValidManifest, false);
      assert.strictEqual(res.status, 'invalid_manifest');
    }
  });

  test('Reject single uppercase letter in middle (char 31)', () => {
    const midChar = 'A';
    const midUpper = validHash.slice(0, 31) + midChar + validHash.slice(32);
    const man = {
      format: 'paralleldoc-integrity-1',
      algorithm: 'SHA-256',
      scope: 'raw-bytes',
      expected_sha256: midUpper
    };
    const res = loader.verifyManifest(validDocBytes, man);
    assert.strictEqual(res.isValidManifest, false);
    assert.strictEqual(res.status, 'invalid_manifest');
  });

  test('Reject alternating case (4a5B6c7D...)', () => {
    const altCase = validHash.split('').map((c, i) => (i % 2 === 1 ? c.toUpperCase() : c.toLowerCase())).join('');
    const man = {
      format: 'paralleldoc-integrity-1',
      algorithm: 'SHA-256',
      scope: 'raw-bytes',
      expected_sha256: altCase
    };
    const res = loader.verifyManifest(validDocBytes, man);
    assert.strictEqual(res.isValidManifest, false);
    assert.strictEqual(res.status, 'invalid_manifest');
  });

  const nonHexExamples = [
    { label: 'char g', val: validHash.slice(0, 63) + 'g' },
    { label: 'char z', val: 'z' + validHash.slice(1) },
    { label: 'char G', val: validHash.slice(0, 63) + 'G' },
    { label: 'hyphen', val: validHash.slice(0, 63) + '-' },
    { label: 'underscore', val: validHash.slice(0, 63) + '_' },
    { label: 'space in middle', val: validHash.slice(0, 32) + ' ' + validHash.slice(33) },
    { label: 'leading space', val: ' ' + validHash.slice(1) },
    { label: 'trailing space', val: validHash.slice(0, 63) + ' ' },
    { label: 'newline char', val: validHash.slice(0, 63) + '\n' },
    { label: 'null byte', val: validHash.slice(0, 63) + '\0' },
    { label: '0x prefix (66 chars)', val: '0x' + validHash },
    { label: '0x prefix (64 chars)', val: '0x' + validHash.slice(2) }
  ];

  for (const ex of nonHexExamples) {
    test(`Reject non-hex character in expected_sha256: ${ex.label}`, () => {
      const man = {
        format: 'paralleldoc-integrity-1',
        algorithm: 'SHA-256',
        scope: 'raw-bytes',
        expected_sha256: ex.val
      };
      const res = loader.verifyManifest(validDocBytes, man);
      assert.strictEqual(res.isValidManifest, false);
      assert.strictEqual(res.status, 'invalid_manifest');
    });
  }

  const badTypes = [
    { label: 'number', val: 1234567890 },
    { label: 'boolean true', val: true },
    { label: 'boolean false', val: false },
    { label: 'null', val: null },
    { label: 'undefined', val: undefined },
    { label: 'object', val: {} },
    { label: 'array', val: [validHash] }
  ];

  for (const bt of badTypes) {
    test(`Reject non-string expected_sha256: ${bt.label}`, () => {
      const man = {
        format: 'paralleldoc-integrity-1',
        algorithm: 'SHA-256',
        scope: 'raw-bytes',
        expected_sha256: bt.val
      };
      const res = loader.verifyManifest(validDocBytes, man);
      assert.strictEqual(res.isValidManifest, false);
      assert.strictEqual(res.status, 'invalid_manifest');
    });
  }

  // ==========================================================================
  // DISCREPANCY 2: MANIFEST SCHEMA ADDITIONAL PROPERTIES & PROPERTY TYPES
  // ==========================================================================
  console.log('\n--- Area 2: Manifest additionalProperties: false and Property Types ---');

  const extraPropTests = [
    { label: 'single extra string', prop: { extra_key: 'value' } },
    { label: 'single extra number', prop: { build_number: 42 } },
    { label: 'single extra boolean', prop: { is_signed: true } },
    { label: 'single extra object', prop: { security: { signed_by: 'alice' } } },
    { label: 'single extra array', prop: { tags: ['v3', 'qa'] } },
    { label: 'single extra null', prop: { comments: null } },
    { label: 'single extra undefined', prop: { note: undefined } },
    { label: 'document_title (unauthorized)', prop: { title: 'Some Title' } },
    { label: 'signature property', prop: { signature: 'sig1234' } },
    { label: 'hash property (alias)', prop: { sha256: validHash } },
    { label: 'multiple extra properties', prop: { foo: 1, bar: 2, baz: 3 } }
  ];

  for (const ep of extraPropTests) {
    test(`Reject manifest with ${ep.label}`, () => {
      const man = Object.assign({
        format: 'paralleldoc-integrity-1',
        algorithm: 'SHA-256',
        scope: 'raw-bytes',
        expected_sha256: validHash
      }, ep.prop);
      const res = loader.verifyManifest(validDocBytes, man);
      assert.strictEqual(res.isValidManifest, false);
      assert.strictEqual(res.status, 'invalid_manifest');
      assert(res.message.includes('additionalProperties: false') || res.message.includes('Недопустимые свойства'));
    });
  }

  // Prototype pollution keys
  test('Reject manifest with own prototype pollution keys', () => {
    const man = {
      format: 'paralleldoc-integrity-1',
      algorithm: 'SHA-256',
      scope: 'raw-bytes',
      expected_sha256: validHash
    };
    Object.defineProperty(man, '__proto_injected', { value: 'danger', enumerable: true });
    const res = loader.verifyManifest(validDocBytes, man);
    assert.strictEqual(res.isValidManifest, false);
    assert.strictEqual(res.status, 'invalid_manifest');
  });

  // Valid document_id and revision
  test('Accept valid string document_id and revision in manifest', () => {
    const man = {
      format: 'paralleldoc-integrity-1',
      algorithm: 'SHA-256',
      scope: 'raw-bytes',
      expected_sha256: validHash,
      document_id: 'doc-alpha',
      revision: 'rev-1'
    };
    const res = loader.verifyManifest(validDocBytes, man, validDoc.metadata);
    assert.strictEqual(res.isValidManifest, true);
    assert.strictEqual(res.status, 'matched');
  });

  test('Accept valid empty string document_id and revision', () => {
    const man = {
      format: 'paralleldoc-integrity-1',
      algorithm: 'SHA-256',
      scope: 'raw-bytes',
      expected_sha256: validHash,
      document_id: '',
      revision: ''
    };
    const res = loader.verifyManifest(validDocBytes, man, { document_id: '', revision: '' });
    assert.strictEqual(res.isValidManifest, true);
    assert.strictEqual(res.status, 'matched');
  });

  // Non-string document_id
  const nonStringDocIds = [
    { label: 'number 123', val: 123 },
    { label: 'boolean true', val: true },
    { label: 'boolean false', val: false },
    { label: 'null', val: null },
    { label: 'object {}', val: {} },
    { label: 'array []', val: ['doc-alpha'] }
  ];

  for (const nsd of nonStringDocIds) {
    test(`Reject non-string document_id in manifest: ${nsd.label}`, () => {
      const man = {
        format: 'paralleldoc-integrity-1',
        algorithm: 'SHA-256',
        scope: 'raw-bytes',
        expected_sha256: validHash,
        document_id: nsd.val
      };
      const res = loader.verifyManifest(validDocBytes, man);
      assert.strictEqual(res.isValidManifest, false);
      assert.strictEqual(res.status, 'invalid_manifest');
      assert(res.message.includes('document_id должен быть строкой'));
    });
  }

  // Non-string revision
  const nonStringRevisions = [
    { label: 'number 1.0', val: 1.0 },
    { label: 'boolean true', val: true },
    { label: 'boolean false', val: false },
    { label: 'null', val: null },
    { label: 'object {}', val: {} },
    { label: 'array []', val: ['rev-1'] }
  ];

  for (const nsr of nonStringRevisions) {
    test(`Reject non-string revision in manifest: ${nsr.label}`, () => {
      const man = {
        format: 'paralleldoc-integrity-1',
        algorithm: 'SHA-256',
        scope: 'raw-bytes',
        expected_sha256: validHash,
        revision: nsr.val
      };
      const res = loader.verifyManifest(validDocBytes, man);
      assert.strictEqual(res.isValidManifest, false);
      assert.strictEqual(res.status, 'invalid_manifest');
      assert(res.message.includes('revision должна быть строкой'));
    });
  }

  // ==========================================================================
  // DISCREPANCY 3: V8 SYNTAX ERROR LOCATOR FALLBACK
  // ==========================================================================
  console.log('\n--- Area 3: V8 Syntax Error Locator Fallback Accuracy ---');

  await testAsync('Deceptive token: unquoted token matching word inside earlier string literal', async () => {
    // Here "BAD_IDENTIFIER" appears inside a string literal on line 5.
    // The actual unquoted syntax error is on line 12!
    // A naive indexOf("BAD_IDENTIFIER") would locate line 5!
    // loader.js must locate line 12!
    const deceptiveJson = [
      '{',
      '  "format": "paralleldoc",',
      '  "version": "3.0",',
      '  "metadata": {',
      '    "title": "Discussion about BAD_IDENTIFIER in string literal",',
      '    "document_id": "doc-deceptive",',
      '    "revision": "rev-1",',
      '    "author_refs": ["auth-1"]',
      '  },',
      '  "authors": [],',
      '  "units": [',
      '    BAD_IDENTIFIER',
      '  ]',
      '}'
    ].join('\n');

    const res = await loader.loadDocument(enc.encode(deceptiveJson));
    assert.strictEqual(res.success, false);
    assert.strictEqual(res.errorType, 'PARSE_ERROR');
    assert.strictEqual(res.line, 12, `Expected syntax error on line 12, got line ${res.line}`);
    assert(res.snippet.includes('BAD_IDENTIFIER'));
    assert(res.snippet.includes('^'));
  });

  await testAsync('Escaped quotes inside strings before unquoted token', async () => {
    // Strings with \" inside must not throw off inString tracking
    const escapedJson = [
      '{',
      '  "format": "paralleldoc",',
      '  "version": "3.0",',
      '  "metadata": {',
      '    "title": "String with \\"escaped quotes\\" and TARGET_TOKEN inside quotes",',
      '    "notes": "Another string with \\\\\\\" triple escape and TARGET_TOKEN"',
      '  },',
      '  "target": TARGET_TOKEN',
      '}'
    ].join('\n');

    const res = await loader.loadDocument(enc.encode(escapedJson));
    assert.strictEqual(res.success, false);
    assert.strictEqual(res.errorType, 'PARSE_ERROR');
    assert.strictEqual(res.line, 8, `Expected syntax error on line 8, got line ${res.line}`);
  });

  await testAsync('Deeply nested syntax error at line 45', async () => {
    const lines = [
      '{',
      '  "format": "paralleldoc",',
      '  "version": "3.0",'
    ];
    for (let i = 4; i < 45; i++) {
      lines.push(`  "key_${i}": "valid_value_${i}",`);
    }
    lines.push('  "bad_line": UNQUOTED_DEEP_VAL,');
    lines.push('  "key_final": 123');
    lines.push('}');
    const deepJson = lines.join('\n');

    const res = await loader.loadDocument(enc.encode(deepJson));
    assert.strictEqual(res.success, false);
    assert.strictEqual(res.errorType, 'PARSE_ERROR');
    assert.strictEqual(res.line, 45, `Expected syntax error at line 45, got line ${res.line}`);
  });

  await testAsync('Syntax error on single line input', async () => {
    const singleLine = '{"format": "paralleldoc", "version": "3.0", "bad": BAD_TOKEN}';
    const res = await loader.loadDocument(enc.encode(singleLine));
    assert.strictEqual(res.success, false);
    assert.strictEqual(res.errorType, 'PARSE_ERROR');
    assert.strictEqual(res.line, 1);
    assert(res.column > 40);
  });

  await testAsync('Trailing comma in object at line 6', async () => {
    const trailingCommaJson = [
      '{',
      '  "format": "paralleldoc",',
      '  "version": "3.0",',
      '  "metadata": {',
      '    "document_id": "d1",',
      '  }',
      '}'
    ].join('\n');

    const res = await loader.loadDocument(enc.encode(trailingCommaJson));
    assert.strictEqual(res.success, false);
    assert.strictEqual(res.errorType, 'PARSE_ERROR');
    // V8 typically flags position at line 6 column 3 or line 5
    assert(res.line >= 5 && res.line <= 6, `Expected error near line 5-6, got line ${res.line}`);
  });

  await testAsync('Single-quoted keys at line 4', async () => {
    const singleQuoteJson = [
      '{',
      '  "format": "paralleldoc",',
      '  "version": "3.0",',
      '  \'single_quoted\': "value"',
      '}'
    ].join('\n');

    const res = await loader.loadDocument(enc.encode(singleQuoteJson));
    assert.strictEqual(res.success, false);
    assert.strictEqual(res.errorType, 'PARSE_ERROR');
    assert.strictEqual(res.line, 4, `Expected line 4, got line ${res.line}`);
  });

  await testAsync('Premature end of input at line 5', async () => {
    const truncatedJson = [
      '{',
      '  "format": "paralleldoc",',
      '  "version": "3.0",',
      '  "metadata": {',
      '    "document_id": "d1"'
    ].join('\n');

    const res = await loader.loadDocument(enc.encode(truncatedJson));
    assert.strictEqual(res.success, false);
    assert.strictEqual(res.errorType, 'PARSE_ERROR');
    assert.strictEqual(res.line, 5, `Expected line 5 for truncated JSON, got line ${res.line}`);
  });

  // Direct tests of locateSyntaxError helper
  test('locateSyntaxError handles null/empty/whitespace inputs without throwing', () => {
    const res1 = loader.locateSyntaxError('', 'Unexpected token');
    assert.deepStrictEqual(res1, { line: 1, col: 1 });

    const res2 = loader.locateSyntaxError('   ', 'Unexpected end of JSON input');
    assert(res2.line >= 1 && res2.col >= 1);
  });

  test('locateSyntaxError parses line X column Y message correctly', () => {
    const res = loader.locateSyntaxError('dummy text', 'JSON.parse: error at line 14 column 27 of the JSON data');
    assert.deepStrictEqual(res, { line: 14, col: 27 });
  });

  test('locateSyntaxError parses position N message correctly', () => {
    const text = 'line 1\nline 2\nline 3';
    // position at 'line 2' (starts at index 7)
    const res = loader.locateSyntaxError(text, 'Unexpected token at position 8');
    assert.strictEqual(res.line, 2);
    assert.strictEqual(res.col, 2);
  });

  console.log('\n=== Challenger M2-r2 Stress Suite Completed ===');
  console.log(`Passed: ${passed}, Failed: ${failed}`);

  if (failures.length > 0) {
    console.error('\nFAILURES RECORDED:');
    for (const f of failures) {
      console.error(`- ${f.name}: ${f.error}`);
    }
  }

  return { passed, failed, failures };
}

runChallengerM2R2Stress().then(res => {
  if (res.failed > 0) {
    process.exit(1);
  }
}).catch(err => {
  console.error('Fatal test error:', err);
  process.exit(1);
});
