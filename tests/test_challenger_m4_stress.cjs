/**
 * tests/test_challenger_m4_stress.cjs — Adversarial Stress Test Suite for Milestone 4 (Node.js).
 * Author: challenger_m4 (Empirical Challenger)
 * Tests src/media.js and src/loader.js across all adversarial vectors.
 */

const assert = require('assert');
const crypto = require('crypto');
const media = require('../src/media.js');
const loader = require('../src/loader.js');

const { MediaValidator, MediaRenderer, parseImageHeader, decodeBase64, sha256Bytes } = media;
const { verifyManifest, computeRawSha256Sync } = loader;

// Standard valid 1x1 PNG bytes
const PNG_1X1 = new Uint8Array([
  0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
  0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
  0x00, 0x00, 0x00, 0x01,  // width: 1
  0x00, 0x00, 0x00, 0x01,  // height: 1
  0x08, 0x06, 0x00, 0x00, 0x00,
  0x1F, 0x15, 0xC4, 0x89,
  0x00, 0x00, 0x00, 0x0A, 0x49, 0x44, 0x41, 0x54,
  0x78, 0x9C, 0x63, 0x00, 0x01, 0x00, 0x00, 0x05,
  0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4,
  0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44,
  0xAE, 0x42, 0x60, 0x82
]);

// Standard valid 1x1 JPEG bytes
const JPEG_1X1 = new Uint8Array([
  0xFF, 0xD8,
  0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01, 0x01, 0x01, 0x00, 0x48, 0x00, 0x48, 0x00, 0x00,
  0xFF, 0xC0, 0x00, 0x0B, 0x08,
  0x00, 0x01,  // height: 1
  0x00, 0x01,  // width: 1
  0x01, 0x01, 0x11, 0x00,
  0xFF, 0xD9
]);

// Standard valid 1x1 WebP VP8X static bytes
const WEBP_VP8X_STATIC = new Uint8Array([
  0x52, 0x49, 0x46, 0x46,
  0x1E, 0x00, 0x00, 0x00,
  0x57, 0x45, 0x42, 0x50,
  0x56, 0x50, 0x38, 0x58,
  0x0A, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00,  // flags: animation bit 1 = 0
  0x00, 0x00, 0x00,        // width - 1 = 0
  0x00, 0x00, 0x00         // height - 1 = 0
]);

let passedCount = 0;
let totalCount = 0;
const findings = [];

function check(desc, fn) {
  totalCount++;
  try {
    fn();
    passedCount++;
  } catch (err) {
    console.error('  ✕ FAIL: ' + desc, err.message);
    throw err;
  }
}

async function runAdversarialSuite() {
  console.log('=== RUNNING CHALLENGER M4 ADVERSARIAL STRESS SUITE (Node.js) ===');

  // 1. Media Corruption & Spoofing
  console.log('\n[1/5] Testing Media Corruption & Spoofing...');

  const corruptBase64List = [
    'data:image/png;base64,invalid!@#$',
    'data:image/png;base64,AAA',
    'data:image/png;base64,AAAAA',
    'data:image/png;base64,AA===',
    'data:image/png;base64,AA AA',
    'data:image/png;base64,',
    'data:image/png;base64',
    'data:image/png,iVBORw0KGgoAAAANSUhEUgAAAAE=',
    'not_a_data_uri_at_all'
  ];

  for (const b64 of corruptBase64List) {
    check('Corrupted base64 rejected: ' + b64.slice(0, 35), () => {
      const res = MediaValidator.validateLocator({ mode: 'embedded', data_uri: b64 });
      assert.strictEqual(res.valid, false);
      assert.strictEqual(res.code, 'ERR_ASSET_CORRUPTED_BASE64');
    });
  }

  // Truncated headers
  const truncatedByteList = [
    new Uint8Array([]),
    new Uint8Array([0x89]),
    new Uint8Array([0x89, 0x50, 0x4E, 0x47]),
    new Uint8Array([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A]),
    new Uint8Array([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]), // 8 bytes PNG
    PNG_1X1.slice(0, 23), // 23 bytes (1 byte short)
    new Uint8Array([0xFF]),
    new Uint8Array([0xFF, 0xD8]),
    new Uint8Array([0xFF, 0xD8, 0xFF]),
    JPEG_1X1.slice(0, 20),
    Buffer.from('RIFF'),
    Buffer.from('RIFF\x00\x00\x00\x00WEBP'),
  ];

  for (const tBytes of truncatedByteList) {
    check('Truncated bytes length ' + tBytes.length + ' handled gracefully', () => {
      for (const mime of ['image/png', 'image/jpeg', 'image/webp']) {
        const res = parseImageHeader(new Uint8Array(tBytes), mime);
        assert.strictEqual(res.valid, false);
      }
    });
  }

  // Bit flips in magic bytes
  check('PNG magic byte 0 flip', () => {
    const flipped = new Uint8Array(PNG_1X1);
    flipped[0] = 0x88;
    const res = parseImageHeader(flipped, 'image/png');
    assert.strictEqual(res.valid, false);
  });

  check('PNG magic byte 1 flip', () => {
    const flipped = new Uint8Array(PNG_1X1);
    flipped[1] = 0x51; // 'Q'
    const res = parseImageHeader(flipped, 'image/png');
    assert.strictEqual(res.valid, false);
  });

  check('PNG IHDR chunk tag corrupt', () => {
    const flipped = new Uint8Array(PNG_1X1);
    flipped[12] = 0x4A; // 'J'
    const res = parseImageHeader(flipped, 'image/png');
    assert.strictEqual(res.valid, false);
  });

  check('PNG zero width in IHDR chunk', () => {
    const zeroW = new Uint8Array(PNG_1X1);
    zeroW[16] = 0; zeroW[17] = 0; zeroW[18] = 0; zeroW[19] = 0;
    const res = parseImageHeader(zeroW, 'image/png');
    assert.strictEqual(res.valid, false);
    assert.strictEqual(res.code, 'ERR_ASSET_DIMENSIONS_MISMATCH');
  });

  check('JPEG SOI flip', () => {
    const flipped = new Uint8Array(JPEG_1X1);
    flipped[0] = 0xFE;
    const res = parseImageHeader(flipped, 'image/jpeg');
    assert.strictEqual(res.valid, false);
  });

  check('JPEG zero height in SOF', () => {
    const zeroH = new Uint8Array(JPEG_1X1);
    zeroH[25] = 0; zeroH[26] = 0;
    const res = parseImageHeader(zeroH, 'image/jpeg');
    assert.strictEqual(res.valid, false);
    assert.strictEqual(res.code, 'ERR_ASSET_CORRUPTED_BASE64');
  });

  check('WebP RIFF flip', () => {
    const flipped = new Uint8Array(WEBP_VP8X_STATIC);
    flipped[3] = 0x44; // 'D'
    const res = parseImageHeader(flipped, 'image/webp');
    assert.strictEqual(res.valid, false);
  });

  // MIME spoofing
  const spoofingAttacks = [
    { name: 'HTML as PNG', payload: Buffer.from('<html><body><script>alert(1)</script></body></html>'), mime: 'image/png' },
    { name: 'SVG as PNG', payload: Buffer.from('<svg xmlns="http://www.w3.org/2000/svg"><circle r="10"/></svg>'), mime: 'image/png' },
    { name: 'SVG as JPEG', payload: Buffer.from('<svg xmlns="http://www.w3.org/2000/svg"><circle r="10"/></svg>'), mime: 'image/jpeg' },
    { name: 'SVG as WebP', payload: Buffer.from('<svg xmlns="http://www.w3.org/2000/svg"><circle r="10"/></svg>'), mime: 'image/webp' },
    { name: 'GIF as PNG', payload: Buffer.from('GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!'), mime: 'image/png' },
    { name: 'PDF as PNG', payload: Buffer.from('%PDF-1.7\n1 0 obj\n<<>>\nendobj\ntrailer'), mime: 'image/png' },
    { name: 'Windows PE as PNG', payload: Buffer.from('MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00'), mime: 'image/png' },
    { name: 'Linux ELF as JPEG', payload: Buffer.from('\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00'), mime: 'image/jpeg' },
    { name: 'ZIP archive as WebP', payload: Buffer.concat([Buffer.from('PK\x03\x04\x14\x00\x00\x00\x08\x00'), Buffer.alloc(10)]), mime: 'image/webp' },
    { name: 'PNG as JPEG', payload: Buffer.from(PNG_1X1), mime: 'image/jpeg' },
    { name: 'JPEG as WebP', payload: Buffer.from(JPEG_1X1), mime: 'image/webp' },
    { name: 'WebP as PNG', payload: Buffer.from(WEBP_VP8X_STATIC), mime: 'image/png' },
  ];

  for (const att of spoofingAttacks) {
    check('MIME spoofing blocked: ' + att.name, () => {
      const res = parseImageHeader(new Uint8Array(att.payload), att.mime);
      assert.strictEqual(res.valid, false);
      assert.strictEqual(res.code, 'ERR_ASSET_MIME_SPOOFING');
    });
  }

  // 2. Animated WebP Detection
  console.log('\n[2/5] Testing Animated WebP Detection...');

  const animFlags = [0x02, 0x03, 0x12, 0x82, 0x22, 0x3E, 0xFF];
  for (const flag of animFlags) {
    check('Animated WebP flag 0x' + flag.toString(16).padStart(2, '0') + ' rejected', () => {
      const animBytes = new Uint8Array(WEBP_VP8X_STATIC);
      animBytes[20] = flag;
      const res = parseImageHeader(animBytes, 'image/webp');
      assert.strictEqual(res.valid, false);
      assert.strictEqual(res.code, 'ERR_ASSET_ANIMATED_WEBP');
    });
  }

  check('WebP with ANIM chunk rejected even if VP8X flag bit 1 is 0', () => {
    const vp8x = Buffer.concat([Buffer.from('VP8X\x0a\x00\x00\x00'), Buffer.alloc(10)]);
    const anim = Buffer.from('ANIM\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00');
    const riffPayload = Buffer.concat([Buffer.from('WEBP'), vp8x, anim]);
    const riffHeader = Buffer.concat([Buffer.from('RIFF'), Buffer.alloc(4)]);
    riffHeader.writeUInt32LE(riffPayload.length, 4);
    const full = Buffer.concat([riffHeader, riffPayload]);

    const res = parseImageHeader(new Uint8Array(full), 'image/webp');
    assert.strictEqual(res.valid, false);
    assert.strictEqual(res.code, 'ERR_ASSET_ANIMATED_WEBP');
  });

  check('WebP with ANMF frame chunk rejected', () => {
    const vp8x = Buffer.concat([Buffer.from('VP8X\x0a\x00\x00\x00'), Buffer.alloc(10)]);
    const anmf = Buffer.concat([Buffer.from('ANMF\x10\x00\x00\x00'), Buffer.alloc(16)]);
    const riffPayload = Buffer.concat([Buffer.from('WEBP'), vp8x, anmf]);
    const riffHeader = Buffer.concat([Buffer.from('RIFF'), Buffer.alloc(4)]);
    riffHeader.writeUInt32LE(riffPayload.length, 4);
    const full = Buffer.concat([riffHeader, riffPayload]);

    const res = parseImageHeader(new Uint8Array(full), 'image/webp');
    assert.strictEqual(res.valid, false);
    assert.strictEqual(res.code, 'ERR_ASSET_ANIMATED_WEBP');
  });

  // 3. Budget Edge Cases
  console.log('\n[3/5] Testing Budget Edge Cases...');

  check('Asset count budget: exactly 50 passes, 51 fails', () => {
    const bState = { totalBytes: 0, count: 49 };
    const a50 = {
      id: 'ast-50', mime: 'image/png', byte_length: PNG_1X1.length, width: 1, height: 1,
      sha256: crypto.createHash('sha256').update(PNG_1X1).digest('hex'),
      locator: { mode: 'embedded', data_uri: 'data:image/png;base64,' + Buffer.from(PNG_1X1).toString('base64') }
    };
    const res50 = MediaValidator.validateAsset(a50, bState);
    assert.strictEqual(res50.valid, true);
    assert.strictEqual(bState.count, 50);

    const a51 = { ...a50, id: 'ast-51' };
    const res51 = MediaValidator.validateAsset(a51, bState);
    assert.strictEqual(res51.valid, false);
    assert.strictEqual(res51.code, 'ERR_DOC_ASSET_COUNT_EXCEEDED');
  });

  check('Total media size budget: 32 MiB boundary check', () => {
    const bState = { totalBytes: 32 * 1024 * 1024, count: 2 };
    const extraAsset = {
      id: 'ast-extra', mime: 'image/png', byte_length: PNG_1X1.length, width: 1, height: 1,
      sha256: crypto.createHash('sha256').update(PNG_1X1).digest('hex'),
      locator: { mode: 'embedded', data_uri: 'data:image/png;base64,' + Buffer.from(PNG_1X1).toString('base64') }
    };
    const res = MediaValidator.validateAsset(extraAsset, bState);
    assert.strictEqual(res.valid, false);
    assert.strictEqual(res.code, 'ERR_DOC_MEDIA_BUDGET_EXCEEDED');
  });

  const dimTests = [
    { w: 4096, h: 4096, valid: true },
    { w: 4096, h: 4097, valid: false },
    { w: 8192, h: 2048, valid: true },
    { w: 8192, h: 2049, valid: false },
    { w: 8193, h: 1, valid: false },
    { w: 1, h: 8193, valid: false },
  ];

  for (const d of dimTests) {
    check('Dimensions ' + d.w + 'x' + d.h + ' px expected ' + (d.valid ? 'VALID' : 'REJECTED'), () => {
      const ast = {
        id: 'ast-d', mime: 'image/png', byte_length: 100, width: d.w, height: d.h,
        locator: { mode: 'relative', path: 'assets/d_' + d.w + '_' + d.h + '.png' }
      };
      const res = MediaValidator.validateAsset(ast);
      if (d.valid) {
        assert.notStrictEqual(res.code, 'ERR_ASSET_DIMENSIONS_EXCEEDED');
      } else {
        assert.strictEqual(res.valid, false);
        assert.strictEqual(res.code, 'ERR_ASSET_DIMENSIONS_EXCEEDED');
      }
    });
  }

  // 4. Locator Security Attacks
  console.log('\n[4/5] Testing Locator Security Attacks...');

  const attackLocators = [
    // Windows drive
    { mode: 'relative', path: 'C:\\Windows\\System32\\cmd.exe' },
    { mode: 'relative', path: 'c:/secret/image.png' },
    { mode: 'relative', path: 'D:\\dump.png' },
    { mode: 'relative', path: 'c:image.png' },
    // UNC
    { mode: 'relative', path: '\\\\server\\share\\file.png' },
    { mode: 'relative', path: '//server/share/file.png' },
    { mode: 'relative', path: '\\\\?\\C:\\cmd.exe' },
    // Schemes
    { mode: 'relative', path: 'file:///etc/passwd' },
    { mode: 'relative', path: 'file:test.png' },
    // Traversal
    { mode: 'relative', path: '../secret.png' },
    { mode: 'relative', path: '../../secret.png' },
    { mode: 'relative', path: 'assets/../../secret.png' },
    { mode: 'relative', path: 'assets\\..\\secret.png' },
    { mode: 'relative', path: 'assets/..' },
    { mode: 'relative', path: '..' },
    // Encoded & Special
    { mode: 'relative', path: 'assets/%2e%2e/secret.png' },
    { mode: 'relative', path: 'assets/%2f/secret.png' },
    { mode: 'relative', path: 'assets/%5c/secret.png' },
    { mode: 'relative', path: 'assets/%25/secret.png' },
    { mode: 'relative', path: 'assets/foo%20bar.png' },
    { mode: 'relative', path: 'assets/foo:bar.png' },
    { mode: 'relative', path: 'assets/img.png?query=1' },
    { mode: 'relative', path: 'assets/img.png#hash' },
    // External
    { mode: 'external', url: 'http://insecure.site/image.png' },
    { mode: 'external', url: 'ftp://files.site/image.png' },
    { mode: 'external', url: 'javascript:alert(1)' },
    { mode: 'external', url: 'https://user:pass@host/img.png' },
    { mode: 'external', url: 'https://admin@host/img.png' },
    { mode: 'external', url: 'https://host/path\\sub/img.png' },
    { mode: 'external', url: 'https://host/path/../img.png' },
    { mode: 'external', url: 'https://host/path/..' },
  ];

  for (const loc of attackLocators) {
    check('Locator attack blocked: ' + (loc.path || loc.url), () => {
      const res = MediaValidator.validateLocator(loc);
      assert.strictEqual(res.valid, false);
      assert.strictEqual(res.code, 'ERR_FORBIDDEN_ASSET_LOCATOR');
    });
  }

  // Non-NFC Unicode
  check('Decomposed Unicode (NFD) relative path blocked', () => {
    const nfdPath = 'assets/' + 'café.png'.normalize('NFD');
    assert.notStrictEqual(nfdPath, nfdPath.normalize('NFC'));
    const res = MediaValidator.validateLocator({ mode: 'relative', path: nfdPath });
    assert.strictEqual(res.valid, false);
    assert.strictEqual(res.code, 'ERR_FORBIDDEN_ASSET_LOCATOR');
  });

  // Check vulnerability: empty password in credentials URL
  check('Vulnerability probe: https://user:@host/img.png', () => {
    const res = MediaValidator.validateLocator({ mode: 'external', url: 'https://user:@host/img.png' });
    if (res.valid) {
      findings.push({
        id: 'FINDING-01-EMPTY-PASSWORD-URL',
        severity: 'MEDIUM',
        description: 'URL with empty password (https://user:@host/img.png) bypasses regex /^https:\\/\\/[^\\/@:]+(:[^\\/@:]+)?@/i'
      });
      console.log('   [!] EMPIRICALLY CONFIRMED VULNERABILITY: https://user:@host/img.png bypassed external locator regex in src/media.js line 398!');
    }
    assert.strictEqual(res.valid, false);
    assert.strictEqual(res.code, 'ERR_FORBIDDEN_ASSET_LOCATOR');
  });

  // M4-r2 edge cases
  const r2EdgeCases = [
    { url: 'https://user:@host/img.png', allow: false, label: 'empty password' },
    { url: 'https://:pass@host/img.png', allow: false, label: 'empty user' },
    { url: 'https://user:pass@host/img.png', allow: false, label: 'user and pass' },
    { url: 'https://@host/img.png', allow: false, label: 'empty user and pass with @' },
    { url: 'https://valid.site/img.png', allow: true, label: 'valid external site' },
    { url: 'https://valid.site/image@2x.png', allow: true, label: '@ in path component' },
    { url: 'https://valid.site/api?q=foo@bar', allow: true, label: '@ in query string' },
    { url: 'https://valid.site/page#header@target', allow: true, label: '@ in fragment' }
  ];

  for (const tc of r2EdgeCases) {
    check(`R2 Edge Case: ${tc.label} (${tc.url})`, () => {
      const res = MediaValidator.validateLocator({ mode: 'external', url: tc.url });
      if (tc.allow) {
        assert.strictEqual(res.valid, true);
      } else {
        assert.strictEqual(res.valid, false);
        assert.strictEqual(res.code, 'ERR_FORBIDDEN_ASSET_LOCATOR');
      }
    });
  }

  // 5. Detached Manifest Permutations
  console.log('\n[5/5] Testing Detached Manifest Permutations (verifyManifest)...');

  const rawDocBytes = Buffer.from(JSON.stringify({ format: 'paralleldoc', version: '3.0' }));
  const actualDocSha = crypto.createHash('sha256').update(rawDocBytes).digest('hex');

  check('Manifest matched', () => {
    const manifest = {
      format: 'paralleldoc-integrity-1',
      algorithm: 'SHA-256',
      scope: 'raw-bytes',
      expected_sha256: actualDocSha,
      document_id: 'doc-01',
      revision: 'rev-1'
    };
    const res = verifyManifest(rawDocBytes, manifest, { document_id: 'doc-01', revision: 'rev-1' });
    assert.strictEqual(res.isValidManifest, true);
    assert.strictEqual(res.status, 'matched');
  });

  check('Manifest mismatch', () => {
    const manifest = {
      format: 'paralleldoc-integrity-1',
      algorithm: 'SHA-256',
      scope: 'raw-bytes',
      expected_sha256: '0'.repeat(64),
      document_id: 'doc-01',
      revision: 'rev-1'
    };
    const res = verifyManifest(rawDocBytes, manifest, { document_id: 'doc-01', revision: 'rev-1' });
    assert.strictEqual(res.isValidManifest, true);
    assert.strictEqual(res.status, 'mismatch');
  });

  check('Manifest different document_id', () => {
    const manifest = {
      format: 'paralleldoc-integrity-1',
      algorithm: 'SHA-256',
      scope: 'raw-bytes',
      expected_sha256: actualDocSha,
      document_id: 'doc-different',
      revision: 'rev-1'
    };
    const res = verifyManifest(rawDocBytes, manifest, { document_id: 'doc-01', revision: 'rev-1' });
    assert.strictEqual(res.status, 'different_document');
  });

  check('Manifest different revision', () => {
    const manifest = {
      format: 'paralleldoc-integrity-1',
      algorithm: 'SHA-256',
      scope: 'raw-bytes',
      expected_sha256: actualDocSha,
      document_id: 'doc-01',
      revision: 'rev-different'
    };
    const res = verifyManifest(rawDocBytes, manifest, { document_id: 'doc-01', revision: 'rev-1' });
    assert.strictEqual(res.status, 'different_document');
  });

  const badManifests = [
    { format: 'paralleldoc-integrity-2', algorithm: 'SHA-256', scope: 'raw-bytes', expected_sha256: 'a'.repeat(64) },
    { format: 'paralleldoc-integrity-1', algorithm: 'SHA-512', scope: 'raw-bytes', expected_sha256: 'a'.repeat(64) },
    { format: 'paralleldoc-integrity-1', algorithm: 'SHA-256', scope: 'normalized-json', expected_sha256: 'a'.repeat(64) },
    { format: 'paralleldoc-integrity-1', algorithm: 'SHA-256', scope: 'raw-bytes', expected_sha256: 'A'.repeat(64) },
    { format: 'paralleldoc-integrity-1', algorithm: 'SHA-256', scope: 'raw-bytes', expected_sha256: 'a'.repeat(63) },
    { format: 'paralleldoc-integrity-1', algorithm: 'SHA-256', scope: 'raw-bytes', expected_sha256: 'a'.repeat(65) },
    { format: 'paralleldoc-integrity-1', algorithm: 'SHA-256', scope: 'raw-bytes', expected_sha256: 'a'.repeat(64), extra_prop: 123 },
    'not json at all {',
    12345
  ];

  for (const bm of badManifests) {
    check('Bad manifest rejected: ' + (typeof bm === 'object' ? JSON.stringify(bm) : bm), () => {
      const res = verifyManifest(rawDocBytes, bm);
      assert.strictEqual(res.isValidManifest, false);
      assert.strictEqual(res.status, 'invalid_manifest');
    });
  }

  console.log('\n======================================================');
  console.log('CHALLENGER M4 SUITE RESULTS: ' + passedCount + ' / ' + totalCount + ' checks PASSED');
  if (findings.length > 0) {
    console.log('Adversarial findings discovered: ' + findings.length);
    for (const f of findings) {
      console.log('  - [' + f.severity + '] ' + f.id + ': ' + f.description);
    }
  }
  console.log('======================================================\n');
}

runAdversarialSuite().catch(err => {
  console.error('Test suite execution failed:', err);
  process.exit(1);
});
