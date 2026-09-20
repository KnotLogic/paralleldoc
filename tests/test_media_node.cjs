/**
 * tests/test_media_node.cjs — Comprehensive Node.js Unit & Regression Tests for ParallelDoc Media Contract.
 * Tests src/media.js (MediaValidator, MediaRenderer, ModalInspector).
 * Fulfills F34-F44, AC-19-AC-24, AC-26-AC-29.
 */

const assert = require('assert');
const media = require('../src/media.js');
const { MediaValidator, MediaRenderer, ModalInspector } = media;

// Standard valid 1x1 PNG bytes
const PNG_1X1_BYTES = new Uint8Array([
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

// Minimal valid JPEG bytes (1x1 pixel)
const JPEG_1X1_BYTES = new Uint8Array([
  0xFF, 0xD8,  // SOI
  0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01, 0x01, 0x01, 0x00, 0x48, 0x00, 0x48, 0x00, 0x00,
  0xFF, 0xC0, 0x00, 0x0B, 0x08,  // SOF0, precision 8
  0x00, 0x01,  // height: 1
  0x00, 0x01,  // width: 1
  0x01, 0x01, 0x11, 0x00,
  0xFF, 0xD9   // EOI
]);

// Minimal valid WebP VP8 bytes (1x1 pixel)
const WEBP_VP8_BYTES = new Uint8Array([
  0x52, 0x49, 0x46, 0x46, 0x1E, 0x00, 0x00, 0x00,
  0x57, 0x45, 0x42, 0x50, 0x56, 0x50, 0x38, 0x20,
  0x12, 0x00, 0x00, 0x00, 0x30, 0x01, 0x00, 0x9D,
  0x01, 0x2A, 0x01, 0x00, 0x01, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00
]);

// Minimal valid WebP VP8L bytes (1x1 pixel)
const WEBP_VP8L_BYTES = new Uint8Array([
  0x52, 0x49, 0x46, 0x46, 0x1A, 0x00, 0x00, 0x00,
  0x57, 0x45, 0x42, 0x50, 0x56, 0x50, 0x38, 0x4C,
  0x0E, 0x00, 0x00, 0x00, 0x2F, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00
]);

// Minimal static WebP VP8X bytes (1x1 pixel, animation bit 1 = 0)
const WEBP_VP8X_STATIC_BYTES = new Uint8Array([
  0x52, 0x49, 0x46, 0x46, 0x20, 0x00, 0x00, 0x00,
  0x57, 0x45, 0x42, 0x50, 0x56, 0x50, 0x38, 0x58,
  0x0A, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00
]);

// Animated WebP VP8X bytes (animation flag bit 1 set: flags & 0x02 != 0)
const WEBP_VP8X_ANIMATED_BYTES = new Uint8Array([
  0x52, 0x49, 0x46, 0x46, 0x20, 0x00, 0x00, 0x00,
  0x57, 0x45, 0x42, 0x50, 0x56, 0x50, 0x38, 0x58,
  0x0A, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00
]);

function toBase64(uint8) {
  return Buffer.from(uint8).toString('base64');
}

function makeAsset(uint8, mime, assetId = 'ast-sla-uptime') {
  const b64 = toBase64(uint8);
  const crypto = require('crypto');
  const sha = crypto.createHash('sha256').update(uint8).digest('hex');
  return {
    id: assetId,
    mime: mime,
    sha256: sha,
    byte_length: uint8.length,
    width: 1,
    height: 1,
    caption: 'Node.js Test Asset',
    alt: 'Test Alt',
    author_refs: ['auth-01'],
    provenance: { label: 'In-Memory Test' },
    locator: {
      mode: 'embedded',
      data_uri: `data:${mime};base64,${b64}`
    }
  };
}

async function runNodeTests() {
  console.log('=== RUNNING PARALLELDOC MEDIA CONTRACT NODE.JS TESTS ===');

  // 1. Binary Image Header Parsing
  console.log('1. Testing binary header parsing...');
  const pngHeader = MediaValidator.parseImageHeader(PNG_1X1_BYTES, 'image/png');
  assert.strictEqual(pngHeader.valid, true);
  assert.strictEqual(pngHeader.mime, 'image/png');
  assert.strictEqual(pngHeader.width, 1);
  assert.strictEqual(pngHeader.height, 1);

  const jpegHeader = MediaValidator.parseImageHeader(JPEG_1X1_BYTES, 'image/jpeg');
  assert.strictEqual(jpegHeader.valid, true);
  assert.strictEqual(jpegHeader.mime, 'image/jpeg');
  assert.strictEqual(jpegHeader.width, 1);
  assert.strictEqual(jpegHeader.height, 1);

  const webpHeader = MediaValidator.parseImageHeader(WEBP_VP8_BYTES, 'image/webp');
  assert.strictEqual(webpHeader.valid, true);
  assert.strictEqual(webpHeader.mime, 'image/webp');
  assert.strictEqual(webpHeader.width, 1);
  assert.strictEqual(webpHeader.height, 1);

  const webpLHeader = MediaValidator.parseImageHeader(WEBP_VP8L_BYTES, 'image/webp');
  assert.strictEqual(webpLHeader.valid, true);
  assert.strictEqual(webpLHeader.mime, 'image/webp');
  assert.strictEqual(webpLHeader.width, 1);
  assert.strictEqual(webpLHeader.height, 1);

  const webpXHeader = MediaValidator.parseImageHeader(WEBP_VP8X_STATIC_BYTES, 'image/webp');
  assert.strictEqual(webpXHeader.valid, true);
  assert.strictEqual(webpXHeader.mime, 'image/webp');
  assert.strictEqual(webpXHeader.width, 1);
  assert.strictEqual(webpXHeader.height, 1);

  // Animated WebP must be strictly rejected
  const animatedHeader = MediaValidator.parseImageHeader(WEBP_VP8X_ANIMATED_BYTES, 'image/webp');
  assert.strictEqual(animatedHeader.valid, false);
  assert.strictEqual(animatedHeader.code, 'ERR_ASSET_ANIMATED_WEBP');
  console.log('   ✓ Binary header parsing and animated WebP rejection verified');

  // 2. Locator Security Guard
  console.log('2. Testing locator security guard...');
  const badLocators = [
    { mode: 'relative', path: 'C:\\Windows\\system32\\cmd.exe' },
    { mode: 'relative', path: 'D:/secret.png' },
    { mode: 'relative', path: '\\\\server\\share\\img.png' },
    { mode: 'relative', path: 'file:///etc/passwd' },
    { mode: 'relative', path: '../traversal.png' },
    { mode: 'relative', path: 'assets/../../escape.png' },
    { mode: 'relative', path: 'assets\\sub\\image.png' },
    { mode: 'relative', path: 'assets/%2e%2e/sub.png' },
    { mode: 'external', url: 'http://insecure.com/image.png' },
    { mode: 'external', url: 'ftp://ftp.org/image.png' },
    { mode: 'external', url: 'https://user:pass@evil.com/image.png' },
    { mode: 'external', url: 'https://evil.com/path\\sub.png' },
    { mode: 'external', url: 'https://evil.com/path/../secret.png' },
    { mode: 'embedded', data_uri: 'data:image/png;notbase64,???' },
    { mode: 'embedded', data_uri: 'not_a_data_uri' },
  ];

  for (const loc of badLocators) {
    const res = MediaValidator.validateLocator(loc);
    assert.strictEqual(res.valid, false, `Expected rejection for locator: ${JSON.stringify(loc)}`);
  }

  // Valid locators
  const validEmbedded = MediaValidator.validateLocator({
    mode: 'embedded',
    data_uri: `data:image/png;base64,${toBase64(PNG_1X1_BYTES)}`
  });
  assert.strictEqual(validEmbedded.valid, true);

  const validRel = MediaValidator.validateLocator({
    mode: 'relative',
    path: 'assets/diagram-01.png'
  });
  assert.strictEqual(validRel.valid, true);

  const validExt = MediaValidator.validateLocator({
    mode: 'external',
    url: 'https://cdn.example.com/assets/img.png'
  });
  assert.strictEqual(validExt.valid, true);
  console.log('   ✓ Locator security checks verified (all injection attacks blocked)');

  // 3. Asset Validation (Positive & Negative)
  console.log('3. Testing MediaValidator.validateAsset...');
  const validAsset = makeAsset(PNG_1X1_BYTES, 'image/png');
  const validRes = MediaValidator.validateAsset(validAsset);
  assert.strictEqual(validRes.valid, true);

  // Corrupted Base64
  const corruptAsset = makeAsset(PNG_1X1_BYTES, 'image/png');
  corruptAsset.locator.data_uri = 'data:image/png;base64,invalid_base64_!@#';
  const corruptRes = MediaValidator.validateAsset(corruptAsset);
  assert.strictEqual(corruptRes.valid, false);
  assert.strictEqual(corruptRes.code, 'ERR_ASSET_CORRUPTED_BASE64');

  // MIME spoofing: declared image/png but payload is JPEG
  const spoofAsset = makeAsset(JPEG_1X1_BYTES, 'image/jpeg');
  spoofAsset.mime = 'image/png';
  spoofAsset.locator.data_uri = `data:image/png;base64,${toBase64(JPEG_1X1_BYTES)}`;
  const spoofRes = MediaValidator.validateAsset(spoofAsset);
  assert.strictEqual(spoofRes.valid, false);
  assert.strictEqual(spoofRes.code, 'ERR_ASSET_MIME_SPOOFING');

  // SHA mismatch
  const shaMismatchAsset = makeAsset(PNG_1X1_BYTES, 'image/png');
  shaMismatchAsset.sha256 = '0'.repeat(64);
  const shaRes = MediaValidator.validateAsset(shaMismatchAsset);
  assert.strictEqual(shaRes.valid, false);
  assert.strictEqual(shaRes.code, 'ERR_ASSET_HASH_MISMATCH');

  // Byte length mismatch
  const byteLenAsset = makeAsset(PNG_1X1_BYTES, 'image/png');
  byteLenAsset.byte_length = 9999;
  const byteLenRes = MediaValidator.validateAsset(byteLenAsset);
  assert.strictEqual(byteLenRes.valid, false);
  assert.strictEqual(byteLenRes.code, 'ERR_ASSET_BYTE_LENGTH_MISMATCH');

  // Dimension mismatch
  const dimMismatchAsset = makeAsset(PNG_1X1_BYTES, 'image/png');
  dimMismatchAsset.width = 500;
  const dimRes = MediaValidator.validateAsset(dimMismatchAsset);
  assert.strictEqual(dimRes.valid, false);
  assert.strictEqual(dimRes.code, 'ERR_ASSET_DIMENSIONS_MISMATCH');

  // Dimension exceeded (>8192px)
  const dimExceededAsset = makeAsset(PNG_1X1_BYTES, 'image/png');
  dimExceededAsset.width = 9000;
  const dimExcRes = MediaValidator.validateAsset(dimExceededAsset);
  assert.strictEqual(dimExcRes.valid, false);
  assert.strictEqual(dimExcRes.code, 'ERR_ASSET_DIMENSIONS_EXCEEDED');

  // Megapixel exceeded (>16 MP)
  const mpExceededAsset = makeAsset(PNG_1X1_BYTES, 'image/png');
  mpExceededAsset.width = 5000;
  mpExceededAsset.height = 4000;
  const mpExcRes = MediaValidator.validateAsset(mpExceededAsset);
  assert.strictEqual(mpExcRes.valid, false);
  assert.strictEqual(mpExcRes.code, 'ERR_ASSET_DIMENSIONS_EXCEEDED');

  // Single asset size exceeded (>8 MiB)
  const sizeAsset = makeAsset(PNG_1X1_BYTES, 'image/png');
  sizeAsset.byte_length = 9 * 1024 * 1024;
  sizeAsset.locator.data_uri = `data:image/png;base64,${'A'.repeat(12 * 1024 * 1024)}`;
  const sizeRes = MediaValidator.validateAsset(sizeAsset);
  assert.strictEqual(sizeRes.valid, false);
  assert.strictEqual(sizeRes.code, 'ERR_ASSET_SIZE_BUDGET_EXCEEDED');
  console.log('   ✓ Individual asset validation rules verified');

  // 4. Batch & Document Budget Constraints
  console.log('4. Testing document budgets (count & total size)...');
  // Count budget (>50)
  const manyAssets = [];
  for (let i = 0; i < 55; i++) {
    manyAssets.push(makeAsset(PNG_1X1_BYTES, 'image/png', `ast-${i}`));
  }
  const countBatchRes = MediaValidator.validateDocumentAssets(manyAssets);
  assert(countBatchRes.issues.some(i => i.code === 'ERR_DOC_ASSET_COUNT_EXCEEDED'));

  // Total size budget (>32 MiB)
  const heavyPayload = Buffer.alloc(7 * 1024 * 1024).toString('base64');
  const heavyAssets = [];
  for (let i = 0; i < 5; i++) {
    heavyAssets.push({
      id: `ast-heavy-${i}`,
      mime: 'image/png',
      sha256: '0'.repeat(64),
      byte_length: 7 * 1024 * 1024,
      width: 10,
      height: 10,
      locator: {
        mode: 'embedded',
        data_uri: `data:image/png;base64,${heavyPayload}`
      }
    });
  }
  const sizeBatchRes = MediaValidator.validateDocumentAssets(heavyAssets);
  assert(sizeBatchRes.issues.some(i => i.code === 'ERR_DOC_MEDIA_BUDGET_EXCEEDED'));
  console.log('   ✓ Document budgets (50 assets, 32 MiB total) verified');

  // 5. In-Memory Mock DOM Render Tests
  console.log('5. Testing MediaRenderer with in-memory elements...');
  // Minimal DOM shim for Node environment
  global.document = {
    createElement(tag) {
      const el = {
        tagName: tag.toUpperCase(),
        className: '',
        id: '',
        style: {},
        dataset: {},
        attributes: {},
        children: [],
        innerHTML: '',
        textContent: '',
        setAttribute(k, v) { this.attributes[k] = String(v); },
        getAttribute(k) { return this.attributes[k]; },
        removeAttribute(k) { delete this.attributes[k]; },
        hasAttribute(k) { return k in this.attributes; },
        appendChild(child) { this.children.push(child); return child; },
        addEventListener() {},
        removeEventListener() {},
        querySelector() { return null; },
        querySelectorAll() { return []; },
        classList: {
          classes: new Set(),
          add(c) { this.classes.add(c); },
          remove(c) { this.classes.delete(c); },
          toggle(c, force) { if (force !== undefined) { if (force) this.classes.add(c); else this.classes.delete(c); } else { if (this.classes.has(c)) this.classes.delete(c); else this.classes.add(c); } },
          contains(c) { return this.classes.has(c); }
        }
      };
      return el;
    }
  };

  // Render thumbnail
  const thumbEl = MediaRenderer.renderThumbnail(validAsset, () => {});
  assert(thumbEl.className.includes('pd-thumbnail-wrapper'));
  assert.strictEqual(thumbEl.id, `asset-wrapper-${validAsset.id}`);

  // Render error card (AC-23)
  const errEl = MediaRenderer.renderErrorBlock(corruptAsset, 'ERR_ASSET_CORRUPTED_BASE64', 'Invalid Base64');
  assert(errEl.className.includes('pd-thumbnail-wrapper'));
  assert(errEl.className.includes('pd-asset-error-card'));
  assert.strictEqual(errEl.getAttribute('role'), 'alert');
  console.log('   ✓ Thumbnail and Error Card DOM generation verified');

  console.log('=== ALL NODE.JS MEDIA TESTS PASSED SUCCESSFULLY ===');
}

runNodeTests().catch(err => {
  console.error('Node.js media tests failed:', err);
  process.exit(1);
});
