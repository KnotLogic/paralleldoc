/**
 * ParallelDoc 3.0 (r2 / V3-ONLY) — Media & Visual Evidence Engine.
 * Strict compliance with Spec r2 §5, §6, §7, §11 (F34-F39, AC-19, AC-20, AC-22, AC-23, AC-24, AC-28).
 *
 * Capabilities:
 * - Raster media verification (PNG, JPEG, static WebP).
 * - Binary header & magic bytes decoding (IHDR, SOF, VP8/VP8L/VP8X).
 * - Animated WebP immediate rejection (ERR_ASSET_ANIMATED_WEBP).
 * - Strict budget enforcement: <=8 MiB asset, <=32 MiB doc, <=50 assets, <=16 MP, <=8192px side.
 * - Asset locator security guard: 0-trust rejection of Windows drive letters, UNC, file:,
 *   directory traversal, backslashes, credentials, %, :, non-HTTPS.
 * - Pre-reserved thumbnail frame (<=240x144px Reading, <=160x96px Dense, contain: layout size paint)
 *   enforcing layout shift delta = 0px <= 2px (AC-22).
 * - Modal 1:1 Pixel Inspector with keyboard panning (Arrow keys, 4 corners), focus trap, and Esc return.
 * - Graceful diagnostic error blocks and placeholders without document collapse (AC-23, AC-28).
 */

(function(root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.ParallelDocMedia = factory();
  }
})(typeof self !== 'undefined' ? self : (typeof globalThis !== 'undefined' ? globalThis : this), function() {
  'use strict';

  // Budget Constants per Spec r2 §5
  const MAX_ASSET_BYTES = 8 * 1024 * 1024;        // 8 MiB = 8,388,608 bytes
  const MAX_DOC_MEDIA_BYTES = 32 * 1024 * 1024;   // 32 MiB = 33,554,432 bytes
  const MAX_DOC_ASSET_COUNT = 50;                 // 50 assets
  const MAX_IMAGE_PIXELS = 16 * 1024 * 1024;      // 16 MP = 16,777,216 pixels
  const MAX_IMAGE_SIDE = 8192;                    // 8,192 pixels

  // Allowed MIME types strictly per Spec r2 §5 (image/jpg is forbidden)
  const ALLOWED_MIMES = new Set(['image/png', 'image/jpeg', 'image/webp']);

  // Pure JS FIPS 180-4 SHA-256 (synchronous, 0 dependencies)
  function sha256Bytes(uint8Array) {
    if (!(uint8Array instanceof Uint8Array)) {
      if (Array.isArray(uint8Array) || (typeof Buffer !== 'undefined' && Buffer.isBuffer(uint8Array))) {
        uint8Array = new Uint8Array(uint8Array);
      } else {
        throw new TypeError('sha256Bytes requires Uint8Array');
      }
    }
    const K = [
      0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
      0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
      0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
      0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
      0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
      0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
      0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
      0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
    ];
    let H0 = 0x6a09e667, H1 = 0xbb67ae85, H2 = 0x3c6ef372, H3 = 0xa54ff53a;
    let H4 = 0x510e527f, H5 = 0x9b05688c, H6 = 0x1f83d9ab, H7 = 0x5be0cd19;

    const len = uint8Array.length;
    const bitLenHi = Math.floor(len / 0x20000000);
    const bitLenLo = (len << 3) >>> 0;
    const rem = (len + 9) % 64;
    const padLen = rem === 0 ? 0 : 64 - rem;
    const totalLen = len + 1 + padLen + 8;

    const padded = new Uint8Array(totalLen);
    padded.set(uint8Array);
    padded[len] = 0x80;

    const view = new DataView(padded.buffer);
    view.setUint32(totalLen - 8, bitLenHi, false);
    view.setUint32(totalLen - 4, bitLenLo, false);

    const W = new Int32Array(64);
    const rotr = (x, n) => (x >>> n) | (x << (32 - n));

    for (let offset = 0; offset < totalLen; offset += 64) {
      for (let t = 0; t < 16; t++) {
        W[t] = view.getInt32(offset + t * 4, false);
      }
      for (let t = 16; t < 64; t++) {
        const s0 = rotr(W[t - 15], 7) ^ rotr(W[t - 15], 18) ^ (W[t - 15] >>> 3);
        const s1 = rotr(W[t - 2], 17) ^ rotr(W[t - 2], 19) ^ (W[t - 2] >>> 10);
        W[t] = (W[t - 16] + s0 + W[t - 7] + s1) | 0;
      }
      let a = H0, b = H1, c = H2, d = H3, e = H4, f = H5, g = H6, h = H7;
      for (let t = 0; t < 64; t++) {
        const S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
        const ch = (e & f) ^ ((~e) & g);
        const temp1 = (h + S1 + ch + K[t] + W[t]) | 0;
        const S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
        const maj = (a & b) ^ (a & c) ^ (b & c);
        const temp2 = (S0 + maj) | 0;
        h = g; g = f; f = e; e = (d + temp1) | 0;
        d = c; c = b; b = a; a = (temp1 + temp2) | 0;
      }
      H0 = (H0 + a) | 0; H1 = (H1 + b) | 0; H2 = (H2 + c) | 0; H3 = (H3 + d) | 0;
      H4 = (H4 + e) | 0; H5 = (H5 + f) | 0; H6 = (H6 + g) | 0; H7 = (H7 + h) | 0;
    }

    const hex = x => (x >>> 0).toString(16).padStart(8, '0');
    return hex(H0) + hex(H1) + hex(H2) + hex(H3) + hex(H4) + hex(H5) + hex(H6) + hex(H7);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  /**
   * Safe Base64 decoding to Uint8Array.
   */
  function decodeBase64(b64) {
    if (typeof b64 !== 'string') {
      throw new Error('Base64 payload must be a string');
    }
    // Strict pattern check: valid base64 characters and padding length
    if (!/^[A-Za-z0-9+/]+={0,2}$/.test(b64) || b64.length % 4 !== 0) {
      throw new Error('Invalid Base64 character or padding');
    }
    if (typeof Buffer !== 'undefined' && typeof Buffer.from === 'function') {
      const buf = Buffer.from(b64, 'base64');
      return new Uint8Array(buf.buffer, buf.byteOffset, buf.byteLength);
    }
    const binStr = atob(b64);
    const len = binStr.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
      bytes[i] = binStr.charCodeAt(i);
    }
    return bytes;
  }

  /**
   * Binary image header parser.
   * Extracts real width, height, MIME, and checks static animation constraints.
   */
  function parseImageHeader(bytes, declaredMime) {
    if (!(bytes instanceof Uint8Array) || bytes.length < 12) {
      return { valid: false, error: 'Слишком короткий двоичный поток (менее 12 байт)', code: 'ERR_ASSET_CORRUPTED_BASE64' };
    }

    // 1. Check PNG: 89 50 4E 47 0D 0A 1A 0A
    if (
      bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4E && bytes[3] === 0x47 &&
      bytes[4] === 0x0D && bytes[5] === 0x0A && bytes[6] === 0x1A && bytes[7] === 0x0A
    ) {
      if (declaredMime !== 'image/png') {
        return { valid: false, error: `Подмена типа: сигнатура PNG, но заявлен '${declaredMime}'`, code: 'ERR_ASSET_MIME_SPOOFING' };
      }
      if (bytes.length < 24) {
        return { valid: false, error: 'Повреждённый чанк IHDR в PNG', code: 'ERR_ASSET_CORRUPTED_BASE64' };
      }
      // IHDR chunk: offset 12..16 must be "IHDR" (0x49, 0x48, 0x44, 0x52)
      if (bytes[12] !== 0x49 || bytes[13] !== 0x48 || bytes[14] !== 0x44 || bytes[15] !== 0x52) {
        return { valid: false, error: 'Отсутствует обязательный первый чанк IHDR в PNG', code: 'ERR_ASSET_CORRUPTED_BASE64' };
      }
      const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
      const width = view.getUint32(16, false);
      const height = view.getUint32(20, false);
      if (width === 0 || height === 0) {
        return { valid: false, error: 'Нулевые размеры в чанке IHDR PNG', code: 'ERR_ASSET_DIMENSIONS_MISMATCH' };
      }
      return { valid: true, mime: 'image/png', width, height, isAnimated: false };
    }

    // 2. Check JPEG: FF D8 FF
    if (bytes[0] === 0xFF && bytes[1] === 0xD8 && bytes[2] === 0xFF) {
      if (declaredMime !== 'image/jpeg') {
        return { valid: false, error: `Подмена типа: сигнатура JPEG, но заявлен '${declaredMime}'`, code: 'ERR_ASSET_MIME_SPOOFING' };
      }
      let offset = 2;
      let width = 0;
      let height = 0;
      let foundSOF = false;

      while (offset < bytes.length - 8) {
        if (bytes[offset] !== 0xFF) {
          offset++;
          continue;
        }
        while (bytes[offset] === 0xFF && offset < bytes.length) {
          offset++;
        }
        if (offset >= bytes.length) break;
        const marker = bytes[offset++];
        // Stop at image data or end
        if (marker === 0xD9 || marker === 0xDA) break;
        // Skip standalone markers without length
        if ((marker >= 0xD0 && marker <= 0xD7) || marker === 0x01 || marker === 0x00) continue;

        if (offset + 2 > bytes.length) break;
        const segLen = (bytes[offset] << 8) | bytes[offset + 1];
        if (segLen < 2) break;

        // SOF markers: SOF0..SOF15 (excluding DHT 0xC4, JPG 0xC8, DAC 0xCC)
        const isSOF = (
          (marker >= 0xC0 && marker <= 0xC3) ||
          (marker >= 0xC5 && marker <= 0xC7) ||
          (marker >= 0xC9 && marker <= 0xCB) ||
          (marker >= 0xCD && marker <= 0xCF)
        );

        if (isSOF && offset + 7 <= bytes.length) {
          height = (bytes[offset + 3] << 8) | bytes[offset + 4];
          width = (bytes[offset + 5] << 8) | bytes[offset + 6];
          foundSOF = true;
          break;
        }
        offset += segLen;
      }

      if (!foundSOF || width === 0 || height === 0) {
        return { valid: false, error: 'Не найден маркер кадра SOF в JPEG или нулевые размеры', code: 'ERR_ASSET_CORRUPTED_BASE64' };
      }
      return { valid: true, mime: 'image/jpeg', width, height, isAnimated: false };
    }

    // 3. Check WebP: RIFF....WEBP
    if (
      bytes[0] === 0x52 && bytes[1] === 0x49 && bytes[2] === 0x46 && bytes[3] === 0x46 &&
      bytes[8] === 0x57 && bytes[9] === 0x45 && bytes[10] === 0x42 && bytes[11] === 0x50
    ) {
      if (declaredMime !== 'image/webp') {
        return { valid: false, error: `Подмена типа: сигнатура WebP, но заявлен '${declaredMime}'`, code: 'ERR_ASSET_MIME_SPOOFING' };
      }
      let offset = 12;
      let width = 0;
      let height = 0;
      let foundDims = false;
      let isAnimated = false;

      while (offset + 8 <= bytes.length) {
        const tag = String.fromCharCode(bytes[offset], bytes[offset + 1], bytes[offset + 2], bytes[offset + 3]);
        const chunkSize = (bytes[offset + 4]) | (bytes[offset + 5] << 8) | (bytes[offset + 6] << 16) | ((bytes[offset + 7] << 24) >>> 0);
        const dataOffset = offset + 8;

        if (tag === 'ANIM' || tag === 'ANMF') {
          isAnimated = true;
        }

        if (tag === 'VP8X' && dataOffset + 10 <= bytes.length) {
          const flags = bytes[dataOffset];
          // Bit 1 (mask 0x02) is animation flag per WebP specification
          if ((flags & 0x02) !== 0) {
            isAnimated = true;
          }
          const wMinus1 = bytes[dataOffset + 4] | (bytes[dataOffset + 5] << 8) | (bytes[dataOffset + 6] << 16);
          const hMinus1 = bytes[dataOffset + 7] | (bytes[dataOffset + 8] << 8) | (bytes[dataOffset + 9] << 16);
          width = wMinus1 + 1;
          height = hMinus1 + 1;
          foundDims = true;
        } else if (tag === 'VP8 ' && dataOffset + 10 <= bytes.length) {
          // Simple lossy VP8
          if (bytes[dataOffset + 3] === 0x9D && bytes[dataOffset + 4] === 0x01 && bytes[dataOffset + 5] === 0x2A) {
            const rawW = bytes[dataOffset + 6] | (bytes[dataOffset + 7] << 8);
            const rawH = bytes[dataOffset + 8] | (bytes[dataOffset + 9] << 8);
            width = rawW & 0x3FFF;
            height = rawH & 0x3FFF;
            foundDims = true;
          }
        } else if (tag === 'VP8L' && dataOffset + 5 <= bytes.length) {
          // Simple lossless VP8L
          if (bytes[dataOffset] === 0x2F) {
            const b0 = bytes[dataOffset + 1];
            const b1 = bytes[dataOffset + 2];
            const b2 = bytes[dataOffset + 3];
            const b3 = bytes[dataOffset + 4];
            width = 1 + (b0 | ((b1 & 0x3F) << 8));
            height = 1 + (((b1 >> 6) | (b2 << 2) | ((b3 & 0x0F) << 10)));
            foundDims = true;
          }
        }

        const paddedSize = chunkSize + (chunkSize & 1);
        offset = dataOffset + paddedSize;
      }

      if (isAnimated) {
        return {
          valid: false,
          error: 'Анимированный WebP запрещен спецификацией r2 (§5)',
          code: 'ERR_ASSET_ANIMATED_WEBP',
          isAnimated: true
        };
      }

      if (!foundDims || width === 0 || height === 0) {
        return { valid: false, error: 'Не удалось извлечь размеры из чанков WebP', code: 'ERR_ASSET_CORRUPTED_BASE64' };
      }
      return { valid: true, mime: 'image/webp', width, height, isAnimated: false };
    }

    // Unrecognized signature
    return {
      valid: false,
      error: `Нераспознанная двоичная сигнатура файла; не соответствует ${declaredMime}`,
      code: 'ERR_ASSET_MIME_SPOOFING'
    };
  }

  /**
   * MediaValidator class — validates asset locators, binary payload, headers, budgets, hashes.
   */
  class MediaValidator {
    /**
     * Binary image header parser.
     */
    static parseImageHeader(bytes, declaredMime) {
      return parseImageHeader(bytes, declaredMime);
    }

    /**
     * Asset Locator Security Guard (AC-24).
     * Enforces zero-trust isolation: rejects Windows drive letters, UNC, file:, traversal, credentials.
     */
    static validateLocator(locator) {
      if (!locator || typeof locator !== 'object') {
        return { valid: false, code: 'ERR_FORBIDDEN_ASSET_LOCATOR', reason: 'Локатор ресурса отсутствует или не является объектом' };
      }

      const mode = locator.mode;
      if (mode === 'embedded') {
        const uri = locator.data_uri;
        if (typeof uri !== 'string' || !uri) {
          return { valid: false, code: 'ERR_ASSET_CORRUPTED_BASE64', reason: 'Отсутствует поле data_uri для embedded ресурса' };
        }
        const match = uri.match(/^data:image\/(png|jpeg|webp);base64,(.+)$/);
        if (!match) {
          return { valid: false, code: 'ERR_ASSET_CORRUPTED_BASE64', reason: 'Недопустимый формат Data URI (требуется data:image/(png|jpeg|webp);base64,...)' };
        }
        const b64Payload = match[2];
        if (!/^[A-Za-z0-9+/]+={0,2}$/.test(b64Payload) || b64Payload.length % 4 !== 0) {
          return { valid: false, code: 'ERR_ASSET_CORRUPTED_BASE64', reason: 'Некорректная Base64 строка в Data URI' };
        }
        return { valid: true, submime: `image/${match[1]}`, base64: b64Payload };
      }

      if (mode === 'relative') {
        const p = locator.path;
        if (typeof p !== 'string' || !p.trim()) {
          return { valid: false, code: 'ERR_FORBIDDEN_ASSET_LOCATOR', reason: 'Путь к относительному ресурсу пуст' };
        }
        // Windows Drive letter
        if (/^[A-Za-z]:/.test(p)) {
          return { valid: false, code: 'ERR_FORBIDDEN_ASSET_LOCATOR', reason: 'Запрещён абсолютный путь с буквой диска Windows (AC-24)' };
        }
        // UNC Share
        if (/^(\\\\|\/\/)/.test(p)) {
          return { valid: false, code: 'ERR_FORBIDDEN_ASSET_LOCATOR', reason: 'Запрещён сетевой путь UNC (AC-24)' };
        }
        // Scheme prefixes (file:, javascript:, http:, data:, etc.)
        if (/^[a-zA-Z][a-zA-Z0-9+-.]*:/.test(p)) {
          return { valid: false, code: 'ERR_FORBIDDEN_ASSET_LOCATOR', reason: 'Запрещены схемы протоколов в относительном пути (AC-24)' };
        }
        // Absolute POSIX
        if (/^\//.test(p)) {
          return { valid: false, code: 'ERR_FORBIDDEN_ASSET_LOCATOR', reason: 'Запрещён абсолютный путь POSIX (AC-24)' };
        }
        // Directory traversal
        if (/(^|\/|\\)\.\.(\/|\\|$)/.test(p)) {
          return { valid: false, code: 'ERR_FORBIDDEN_ASSET_LOCATOR', reason: 'Запрещен выход за пределы каталога (.. traversal, AC-24)' };
        }
        // Backslashes
        if (/\\/.test(p)) {
          return { valid: false, code: 'ERR_FORBIDDEN_ASSET_LOCATOR', reason: 'Запрещены обратные косые черты (требуется POSIX slash /, AC-24)' };
        }
        // Encoded traversal or forbidden characters % and : per Spec r2 §5 line 130
        if (/%2e/i.test(p) || /%2f/i.test(p) || /%5c/i.test(p) || /%/i.test(p)) {
          return { valid: false, code: 'ERR_FORBIDDEN_ASSET_LOCATOR', reason: 'Символ % запрещён в относительном имени файла (§5)' };
        }
        if (/:/.test(p)) {
          return { valid: false, code: 'ERR_FORBIDDEN_ASSET_LOCATOR', reason: 'Символ : запрещён в относительном имени файла (§5)' };
        }
        if (/[?#]/.test(p)) {
          return { valid: false, code: 'ERR_FORBIDDEN_ASSET_LOCATOR', reason: 'Символы ? и # запрещены в относительном пути' };
        }
        // Unicode NFC check
        if (p !== p.normalize('NFC')) {
          return { valid: false, code: 'ERR_FORBIDDEN_ASSET_LOCATOR', reason: 'Путь должен быть нормализован по форме Unicode NFC' };
        }
        return { valid: true, path: p };
      }

      if (mode === 'external') {
        const u = locator.url;
        if (typeof u !== 'string' || !u.trim()) {
          return { valid: false, code: 'ERR_FORBIDDEN_ASSET_LOCATOR', reason: 'URL внешнего ресурса пуст' };
        }
        if (!/^https:\/\//i.test(u)) {
          return { valid: false, code: 'ERR_FORBIDDEN_ASSET_LOCATOR', reason: 'Внешние ресурсы должны строго использовать протокол https:// (AC-24)' };
        }
        if (/^https:\/\/[^/?#]*@/i.test(u)) {
          return { valid: false, code: 'ERR_FORBIDDEN_ASSET_LOCATOR', reason: 'Запрещены учетные данные (credentials) в URL (AC-24)' };
        }
        if (/\\/.test(u)) {
          return { valid: false, code: 'ERR_FORBIDDEN_ASSET_LOCATOR', reason: 'Запрещены обратные косые черты в URL' };
        }
        if (/\/\.\.(\/|$)/.test(u)) {
          return { valid: false, code: 'ERR_FORBIDDEN_ASSET_LOCATOR', reason: 'Запрещен выход за пределы пути (..) в URL' };
        }
        return { valid: true, url: u };
      }

      return { valid: false, code: 'ERR_FORBIDDEN_ASSET_LOCATOR', reason: `Неподдерживаемый режим локатора: '${mode}'` };
    }

    /**
     * Validates an individual asset against media contract, security, budgets, and hashes.
     */
    static validateAsset(asset, budgetState = { totalBytes: 0, count: 0 }) {
      if (!asset || typeof asset !== 'object') {
        return { valid: false, code: 'ERR_ASSET_CORRUPTED_BASE64', reason: 'Объект вложения повреждён или пуст' };
      }

      const assetId = asset.id || 'unknown-asset';

      // 1. MIME check
      if (!ALLOWED_MIMES.has(asset.mime)) {
        return {
          valid: false,
          code: 'ERR_ASSET_INVALID_MIME',
          reason: `Недопустимый MIME тип '${asset.mime}'; разрешены строго image/png, image/jpeg, image/webp (§5)`
        };
      }

      // 2. Declared dimensions budget check
      if (asset.width > MAX_IMAGE_SIDE || asset.height > MAX_IMAGE_SIDE) {
        return {
          valid: false,
          code: 'ERR_ASSET_DIMENSIONS_EXCEEDED',
          reason: `Сторона изображения (${asset.width}x${asset.height}) превышает лимит ${MAX_IMAGE_SIDE}px (§5)`
        };
      }
      if (asset.width * asset.height > MAX_IMAGE_PIXELS) {
        return {
          valid: false,
          code: 'ERR_ASSET_DIMENSIONS_EXCEEDED',
          reason: `Площадь изображения (${asset.width * asset.height} px) превышает лимит 16 MP (${MAX_IMAGE_PIXELS} px) (§5)`
        };
      }

      // 3. Locator security guard
      const locRes = this.validateLocator(asset.locator);
      if (!locRes.valid) {
        return { valid: false, code: locRes.code, reason: locRes.reason };
      }

      // 4. Non-embedded modes (relative, external) are informational placeholders
      if (asset.locator.mode === 'relative') {
        return {
          valid: true,
          isPlaceholder: true,
          mode: 'relative',
          placeholderText: 'Требуется пакет вложений',
          path: asset.locator.path,
          asset
        };
      }
      if (asset.locator.mode === 'external') {
        let domain = 'external';
        try {
          const u = new URL(asset.locator.url);
          domain = u.hostname;
        } catch (_) {}
        return {
          valid: true,
          isPlaceholder: true,
          mode: 'external',
          placeholderText: 'Внешний ресурс; не загружен',
          domain,
          url: asset.locator.url,
          asset
        };
      }

      // 5. Embedded Mode — Binary Header, Budget, Length, Hash verification
      const b64 = locRes.base64;

      // Pre-flight length check
      if (b64.length * 0.75 > MAX_ASSET_BYTES * 1.05) {
        return {
          valid: false,
          code: 'ERR_ASSET_SIZE_BUDGET_EXCEEDED',
          reason: `Размер вложения превышает лимит 8 MiB (${MAX_ASSET_BYTES} байт)`
        };
      }

      let bytes;
      try {
        bytes = decodeBase64(b64);
      } catch (e) {
        return {
          valid: false,
          code: 'ERR_ASSET_CORRUPTED_BASE64',
          reason: `Сбой декодирования Base64: ${e.message}`
        };
      }

      // Per-asset byte length budget (8 MiB)
      if (bytes.length > MAX_ASSET_BYTES) {
        return {
          valid: false,
          code: 'ERR_ASSET_SIZE_BUDGET_EXCEEDED',
          reason: `Фактический размер (${bytes.length} байт) превышает лимит 8 MiB (${MAX_ASSET_BYTES} байт)`
        };
      }

      budgetState.totalBytes += bytes.length;
      budgetState.count += 1;

      if (budgetState.count > MAX_DOC_ASSET_COUNT) {
        return {
          valid: false,
          code: 'ERR_DOC_ASSET_COUNT_EXCEEDED',
          reason: `Превышено допустимое число медиа-вложений в документе (максимум ${MAX_DOC_ASSET_COUNT})`
        };
      }
      if (budgetState.totalBytes > MAX_DOC_MEDIA_BYTES) {
        return {
          valid: false,
          code: 'ERR_DOC_MEDIA_BUDGET_EXCEEDED',
          reason: `Суммарный объем медиа-вложений (${budgetState.totalBytes} байт) превышает лимит 32 MiB (${MAX_DOC_MEDIA_BYTES} байт)`
        };
      }

      // Declared byte_length match
      if (asset.byte_length !== bytes.length) {
        return {
          valid: false,
          code: 'ERR_ASSET_BYTE_LENGTH_MISMATCH',
          reason: `Несовпадение размера: заявлено ${asset.byte_length} байт, фактически ${bytes.length} байт`
        };
      }

      // Binary magic bytes and format check
      const hdr = parseImageHeader(bytes, asset.mime);
      if (!hdr.valid) {
        return {
          valid: false,
          code: hdr.code || 'ERR_ASSET_MIME_SPOOFING',
          reason: hdr.error
        };
      }

      // Header dimensions match declared dimensions
      if (hdr.width !== asset.width || hdr.height !== asset.height) {
        return {
          valid: false,
          code: 'ERR_ASSET_DIMENSIONS_MISMATCH',
          reason: `Несовпадение геометрии: заявлено ${asset.width}x${asset.height} px, в заголовке файла ${hdr.width}x${hdr.height} px`
        };
      }

      // Compute binary SHA-256
      const actualSha = sha256Bytes(bytes);
      if (actualSha.toLowerCase() !== String(asset.sha256).toLowerCase()) {
        return {
          valid: false,
          code: 'ERR_ASSET_HASH_MISMATCH',
          reason: `Несовпадение SHA-256: заявлен '${asset.sha256}', фактически вычислен '${actualSha}'`,
          expectedSha: asset.sha256,
          actualSha
        };
      }

      return {
        valid: true,
        bytes,
        actualSha,
        width: hdr.width,
        height: hdr.height,
        mime: hdr.mime,
        asset
      };
    }

    /**
     * Batch validates all assets in a document.
     */
    static validateDocumentAssets(assets) {
      const results = new Map();
      const budgetState = { totalBytes: 0, count: 0 };
      const issues = [];

      if (!Array.isArray(assets)) {
        return { results, budgetState, issues };
      }

      if (assets.length > MAX_DOC_ASSET_COUNT) {
        issues.push({
          code: 'ERR_DOC_ASSET_COUNT_EXCEEDED',
          message: `Число вложений (${assets.length}) превышает лимит ${MAX_DOC_ASSET_COUNT}`
        });
      }

      for (let i = 0; i < assets.length; i++) {
        const asset = assets[i];
        if (!asset || !asset.id) continue;
        const res = this.validateAsset(asset, budgetState);
        results.set(asset.id, res);
        if (!res.valid) {
          issues.push({
            assetId: asset.id,
            code: res.code,
            message: res.reason
          });
        }
      }

      return { results, budgetState, issues };
    }

    /**
     * Alias for batch validation returning Map<assetId, validationResult>.
     */
    static validateAll(assets) {
      return this.validateDocumentAssets(assets).results;
    }
  }

  /**
   * MediaRenderer — renders pre-reserved geometry thumbnails, error cards, and placeholders.
   */
  class MediaRenderer {
    /**
     * Master render entry point for an asset in a unit card.
     */
    static renderAsset(asset, validationResult, onOpenModal) {
      if (!validationResult || !validationResult.valid) {
        const code = validationResult ? validationResult.code : 'ERR_ASSET_UNAVAILABLE';
        const reason = validationResult ? validationResult.reason : 'Ошибка валидации вложения';
        return this.renderErrorBlock(asset, code, reason);
      }

      if (validationResult.isPlaceholder) {
        return this.renderPlaceholder(asset, validationResult);
      }

      return this.renderThumbnail(asset, onOpenModal);
    }

    /**
     * Renders a valid thumbnail inside pre-reserved geometric bounding frame.
     * Enforces aspect ratio preservation and layout shift delta <= 2px (AC-19, AC-22).
     */
    static renderThumbnail(asset, onOpenModal) {
      const wrapper = document.createElement('div');
      wrapper.className = 'pd-thumbnail-wrapper';
      wrapper.id = `asset-wrapper-${asset.id}`;

      const triggerBtn = document.createElement('button');
      triggerBtn.type = 'button';
      triggerBtn.className = 'pd-thumbnail-trigger pd-btn';
      triggerBtn.id = `thumb-btn-${asset.id}`;
      triggerBtn.dataset.assetId = asset.id;
      triggerBtn.setAttribute('aria-haspopup', 'dialog');
      triggerBtn.setAttribute(
        'aria-label',
        `Просмотреть полноразмерное изображение: ${asset.caption || asset.id} (${asset.width}×${asset.height} px)`
      );

      const frame = document.createElement('div');
      frame.className = 'pd-thumbnail-frame';

      const img = document.createElement('img');
      img.className = 'pd-thumbnail-img';
      img.src = asset.locator.data_uri;
      img.alt = asset.alt || asset.caption || 'Изображение ParallelDoc';
      img.width = asset.width;
      img.height = asset.height;
      img.loading = 'lazy';

      const zoomBadge = document.createElement('span');
      zoomBadge.className = 'pd-thumbnail-badge-zoom';
      zoomBadge.setAttribute('aria-hidden', 'true');
      zoomBadge.innerHTML = `
        <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="7" cy="7" r="5"/>
          <line x1="11" y1="11" x2="15" y2="15"/>
        </svg>
        1:1
      `;

      frame.appendChild(img);
      frame.appendChild(zoomBadge);
      triggerBtn.appendChild(frame);

      // Caption bar
      const captionBar = document.createElement('div');
      captionBar.className = 'pd-asset-caption-bar';

      const idTag = document.createElement('span');
      idTag.className = 'pd-asset-id-tag';
      idTag.textContent = asset.id;

      const captionText = document.createElement('span');
      captionText.className = 'pd-asset-caption-text';
      captionText.title = asset.caption || '';
      captionText.textContent = asset.caption || '';

      const dimTag = document.createElement('span');
      dimTag.className = 'pd-asset-dim-tag';
      dimTag.textContent = `${asset.width}×${asset.height}`;

      captionBar.appendChild(idTag);
      captionBar.appendChild(captionText);
      captionBar.appendChild(dimTag);

      wrapper.appendChild(triggerBtn);
      wrapper.appendChild(captionBar);

      // Wire modal trigger
      triggerBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (typeof onOpenModal === 'function') {
          onOpenModal(asset, triggerBtn);
        }
      });

      return wrapper;
    }

    /**
     * Diagnostic Error Block (AC-23, AC-28).
     * Rendered inside the exact same frame bounding box to guarantee layout shift = 0px <= 2px.
     */
    static renderErrorBlock(asset, code, reason) {
      const assetId = asset ? asset.id : 'unknown';
      const caption = asset ? (asset.caption || 'Медиа-вложение') : 'Медиа-вложение';

      const wrapper = document.createElement('div');
      wrapper.className = 'pd-thumbnail-wrapper pd-asset-error-card';
      wrapper.id = `asset-error-${assetId}`;
      wrapper.setAttribute('role', 'alert');
      wrapper.setAttribute('aria-label', `Ошибка медиа-вложения ${assetId}: ${reason}`);

      const frame = document.createElement('div');
      frame.className = 'pd-thumbnail-frame pd-asset-frame-error';

      const errorContent = document.createElement('div');
      errorContent.className = 'pd-asset-error-content';
      errorContent.innerHTML = `
        <span class="pd-asset-error-icon" aria-hidden="true">⚠️</span>
        <span class="pd-asset-error-code">${escapeHtml(code)}</span>
        <div class="pd-asset-error-diagnostic">
          <strong>Сбой проверки:</strong> ${escapeHtml(reason)}
        </div>
      `;
      frame.appendChild(errorContent);
      wrapper.appendChild(frame);

      // Caption bar
      const captionBar = document.createElement('div');
      captionBar.className = 'pd-asset-caption-bar';

      const idTag = document.createElement('span');
      idTag.className = 'pd-asset-id-tag';
      idTag.textContent = assetId;

      const captionText = document.createElement('span');
      captionText.className = 'pd-asset-caption-text';
      captionText.title = caption;
      captionText.textContent = caption;

      captionBar.appendChild(idTag);
      captionBar.appendChild(captionText);

      if (asset && asset.width && asset.height) {
        const dimTag = document.createElement('span');
        dimTag.className = 'pd-asset-dim-tag';
        dimTag.textContent = `${asset.width}×${asset.height}`;
        captionBar.appendChild(dimTag);
      }

      wrapper.appendChild(captionBar);

      return wrapper;
    }

    /**
     * Informational Placeholder for relative / external assets (AC-22).
     * Zero filesystem access, zero outbound network requests.
     */
    static renderPlaceholder(asset, placeholderInfo) {
      const wrapper = document.createElement('div');
      wrapper.className = 'pd-thumbnail-wrapper pd-asset-placeholder-card';
      wrapper.id = `asset-placeholder-${asset.id}`;
      wrapper.setAttribute('role', 'status');
      wrapper.setAttribute('aria-label', `Вложение ${asset.id}: ${placeholderInfo.placeholderText}`);

      const frame = document.createElement('div');
      frame.className = 'pd-thumbnail-frame pd-asset-frame-placeholder';

      const content = document.createElement('div');
      content.className = 'pd-asset-placeholder-content';
      content.innerHTML = `
        <span class="pd-asset-placeholder-icon" aria-hidden="true">🖼️</span>
        <span class="pd-asset-placeholder-badge">${escapeHtml(placeholderInfo.placeholderText)}</span>
        <span class="pd-asset-placeholder-sub">${escapeHtml(placeholderInfo.domain || placeholderInfo.path || '')}</span>
      `;
      frame.appendChild(content);
      wrapper.appendChild(frame);

      const captionBar = document.createElement('div');
      captionBar.className = 'pd-asset-caption-bar';
      captionBar.innerHTML = `
        <span class="pd-asset-id-tag">${escapeHtml(asset.id)}</span>
        <span class="pd-asset-caption-text" title="${escapeHtml(asset.caption || '')}">${escapeHtml(asset.caption || '')}</span>
        <span class="pd-asset-dim-tag">${asset.width}×${asset.height}</span>
      `;
      wrapper.appendChild(captionBar);

      if (asset.alt) {
        const altP = document.createElement('p');
        altP.className = 'pd-asset-alt';
        altP.innerHTML = `<em>Alt: ${escapeHtml(asset.alt)}</em>`;
        wrapper.appendChild(altP);
      }

      return wrapper;
    }

    /**
     * Missing asset block for dangling asset references.
     */
    static renderMissingAssetBlock(assetId) {
      return this.renderErrorBlock(
        { id: assetId, caption: 'Отсутствующий ресурс', alt: '' },
        'ERR_DANGLING_ASSET_REF',
        `Ресурс '${assetId}' указан в unit.asset_ids, но отсутствует в doc.assets`
      );
    }
  }

  /**
   * ModalInspector — Fullscreen 1:1 Pixel Modal Dialog.
   * Fulfills F37, AC-20, AC-38, AC-39:
   * - 1:1 natural pixel zoom (naturalWidth x naturalHeight).
   * - Fit-to-screen mode.
   * - Stepped zoom (25% - 400%).
   * - Keyboard panning with Arrow keys reaching all 4 corners.
   * - Escape key closing modal and restoring focus to origin thumbnail trigger.
   * - Strict focus trap within dialog.
   * - Scroll lock on document.body.
   */
  class ModalInspector {
    constructor(modalEl = null) {
      this.modalEl = modalEl || document.getElementById('pd-modal-inspector');
      this.currentAsset = null;
      this.lastFocusedElement = null;
      this.zoomMode = '1:1'; // '1:1', 'fit', or 'custom'
      this.zoomScale = 1.0;
      this.boundKeyDown = this.handleKeyDown.bind(this);

      if (this.modalEl) {
        this.initDOMRefs();
        this.bindEvents();
      }
    }

    initDOMRefs() {
      this.backdropEl = this.modalEl.querySelector('.pd-modal-backdrop');
      this.viewportEl = this.modalEl.querySelector('.pd-modal-viewport') || this.modalEl.querySelector('#modal-viewport');
      this.canvasWrapperEl = this.modalEl.querySelector('.pd-modal-canvas-wrapper');
      this.imgEl = this.modalEl.querySelector('.pd-modal-img') || this.modalEl.querySelector('#modal-image');
      this.titleEl = this.modalEl.querySelector('#modal-asset-caption');
      this.idEl = this.modalEl.querySelector('#modal-asset-id');
      this.dimsEl = this.modalEl.querySelector('#modal-asset-dims');
      this.sizeEl = this.modalEl.querySelector('#modal-asset-size');
      this.mimeEl = this.modalEl.querySelector('#modal-asset-mime');
      this.shaEl = this.modalEl.querySelector('#modal-asset-sha');
      this.altEl = this.modalEl.querySelector('#modal-asset-alt');

      this.btnFit = this.modalEl.querySelector('#modal-btn-fit');
      this.btn100 = this.modalEl.querySelector('#modal-btn-100');
      this.btnZoomIn = this.modalEl.querySelector('#modal-btn-zoom-in');
      this.btnZoomOut = this.modalEl.querySelector('#modal-btn-zoom-out');
      this.btnClose = this.modalEl.querySelector('#modal-btn-close');
    }

    bindEvents() {
      if (this.btnClose) {
        this.btnClose.addEventListener('click', () => this.close());
      }
      if (this.backdropEl) {
        this.backdropEl.addEventListener('click', () => this.close());
      }
      if (this.btnFit) {
        this.btnFit.addEventListener('click', () => this.setZoomMode('fit'));
      }
      if (this.btn100) {
        this.btn100.addEventListener('click', () => this.setZoomMode('1:1'));
      }
      if (this.btnZoomIn) {
        this.btnZoomIn.addEventListener('click', () => this.adjustZoom(0.25));
      }
      if (this.btnZoomOut) {
        this.btnZoomOut.addEventListener('click', () => this.adjustZoom(-0.25));
      }

      // Copy SHA-256 button inside footer
      if (this.shaEl) {
        this.shaEl.addEventListener('click', () => {
          if (this.currentAsset && this.currentAsset.sha256) {
            navigator.clipboard.writeText(this.currentAsset.sha256);
            const orig = this.shaEl.textContent;
            this.shaEl.textContent = 'Скопировано!';
            setTimeout(() => { this.shaEl.textContent = orig; }, 1200);
          }
        });
      }
    }

    isOpen() {
      return this.modalEl && this.modalEl.style.display !== 'none' && !this.modalEl.hasAttribute('hidden');
    }

    /**
     * Opens modal dialog, renders asset, locks body scroll, traps focus.
     */
    open(asset, originTriggerEl = null) {
      if (!this.modalEl) return;
      this.currentAsset = asset;
      this.lastFocusedElement = originTriggerEl || document.activeElement;

      // Populate metadata
      if (this.titleEl) this.titleEl.textContent = asset.caption || asset.id;
      if (this.idEl) this.idEl.textContent = asset.id;
      if (this.dimsEl) this.dimsEl.textContent = `${asset.width} × ${asset.height} px`;
      if (this.sizeEl) {
        const kb = (asset.byte_length / 1024).toFixed(1);
        this.sizeEl.textContent = `${kb} KB`;
      }
      if (this.mimeEl) this.mimeEl.textContent = asset.mime;
      if (this.shaEl) {
        this.shaEl.textContent = asset.sha256;
        this.shaEl.title = 'Нажмите, чтобы скопировать 64-символьный SHA-256';
      }
      if (this.altEl) this.altEl.textContent = asset.alt ? `Alt: ${asset.alt}` : '';

      // Set image source
      if (this.imgEl) {
        this.imgEl.src = asset.locator.data_uri;
        this.imgEl.alt = asset.alt || asset.caption || '';
      }

      // Display modal and lock body
      this.modalEl.removeAttribute('hidden');
      this.modalEl.style.display = 'flex';
      document.body.classList.add('pd-modal-open');

      // Default to 1:1 mode per Spec AC-20
      this.setZoomMode('1:1');

      // Add global keyboard listener
      window.addEventListener('keydown', this.boundKeyDown, true);

      // Shift focus to close button or viewport
      setTimeout(() => {
        if (this.viewportEl) {
          this.viewportEl.focus();
        } else if (this.btnClose) {
          this.btnClose.focus();
        }
      }, 30);
    }

    /**
     * Closes modal dialog, unlocks body scroll, restores focus to origin thumbnail trigger button (AC-20).
     */
    close() {
      if (!this.isOpen()) return;

      window.removeEventListener('keydown', this.boundKeyDown, true);

      this.modalEl.setAttribute('hidden', '');
      this.modalEl.style.display = 'none';
      document.body.classList.remove('pd-modal-open');

      // Return focus to triggering button (AC-20, AC-38)
      if (this.lastFocusedElement && typeof this.lastFocusedElement.focus === 'function') {
        this.lastFocusedElement.focus();
      }
      this.currentAsset = null;
    }

    /**
     * Sets zoom mode: '1:1' (natural pixels), 'fit' (fit-to-screen), or custom scale.
     */
    setZoomMode(mode, customScale = null) {
      this.zoomMode = mode;
      if (!this.imgEl || !this.currentAsset) return;

      if (mode === '1:1') {
        this.zoomScale = 1.0;
        this.imgEl.classList.remove('mode-fit');
        this.imgEl.classList.add('mode-1to1');
        this.imgEl.style.maxWidth = 'none';
        this.imgEl.style.maxHeight = 'none';
        this.imgEl.style.width = `${this.currentAsset.width}px`;
        this.imgEl.style.height = `${this.currentAsset.height}px`;
        this.imgEl.style.objectFit = 'none';
        if (this.btn100) this.btn100.classList.add('active');
        if (this.btnFit) this.btnFit.classList.remove('active');
      } else if (mode === 'fit') {
        this.zoomScale = 1.0;
        this.imgEl.classList.remove('mode-1to1');
        this.imgEl.classList.add('mode-fit');
        this.imgEl.style.maxWidth = '100%';
        this.imgEl.style.maxHeight = '100%';
        this.imgEl.style.width = 'auto';
        this.imgEl.style.height = 'auto';
        this.imgEl.style.objectFit = 'contain';
        if (this.btnFit) this.btnFit.classList.add('active');
        if (this.btn100) this.btn100.classList.remove('active');
      } else if (mode === 'custom' && typeof customScale === 'number') {
        this.zoomScale = Math.max(0.25, Math.min(4.0, customScale));
        this.imgEl.classList.remove('mode-fit');
        this.imgEl.classList.add('mode-1to1');
        this.imgEl.style.maxWidth = 'none';
        this.imgEl.style.maxHeight = 'none';
        this.imgEl.style.width = `${Math.round(this.currentAsset.width * this.zoomScale)}px`;
        this.imgEl.style.height = `${Math.round(this.currentAsset.height * this.zoomScale)}px`;
        this.imgEl.style.objectFit = 'none';
        if (this.btnFit) this.btnFit.classList.remove('active');
        if (this.btn100) this.btn100.classList.toggle('active', Math.abs(this.zoomScale - 1.0) < 0.01);
      }
    }

    adjustZoom(delta) {
      const nextScale = (this.zoomScale || 1.0) + delta;
      this.setZoomMode('custom', nextScale);
    }

    /**
     * Pan viewport scroll position.
     */
    pan(dx, dy) {
      if (!this.viewportEl) return;
      this.viewportEl.scrollLeft += dx;
      this.viewportEl.scrollTop += dy;
    }

    /**
     * Scroll directly to one of the 4 corners (AC-20 mathematical verification).
     */
    scrollToCorner(corner) {
      if (!this.viewportEl) return;
      const maxScrollX = Math.max(0, this.viewportEl.scrollWidth - this.viewportEl.clientWidth);
      const maxScrollY = Math.max(0, this.viewportEl.scrollHeight - this.viewportEl.clientHeight);

      switch (corner) {
        case 'top-left':
          this.viewportEl.scrollLeft = 0;
          this.viewportEl.scrollTop = 0;
          break;
        case 'top-right':
          this.viewportEl.scrollLeft = maxScrollX;
          this.viewportEl.scrollTop = 0;
          break;
        case 'bottom-left':
          this.viewportEl.scrollLeft = 0;
          this.viewportEl.scrollTop = maxScrollY;
          break;
        case 'bottom-right':
          this.viewportEl.scrollLeft = maxScrollX;
          this.viewportEl.scrollTop = maxScrollY;
          break;
      }
    }

    /**
     * Keyboard handling:
     * - Escape: Close modal and restore focus.
     * - Arrows: Pan viewport (80px / 240px with Shift) reaching all 4 corners.
     * - Home / End: Top-left / Bottom-right corner jump.
     * - Tab / Shift+Tab: Focus trap.
     * - 0 / 1: Mode switch (0: fit, 1: 100%).
     */
    handleKeyDown(e) {
      if (!this.isOpen()) return;

      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        this.close();
        return;
      }

      // Shortcut 0: fit, 1: 100%
      if (e.key === '0' && !e.ctrlKey && !e.altKey && !e.metaKey) {
        e.preventDefault();
        this.setZoomMode('fit');
        return;
      }
      if (e.key === '1' && !e.ctrlKey && !e.altKey && !e.metaKey) {
        e.preventDefault();
        this.setZoomMode('1:1');
        return;
      }
      if (e.key === '+' || e.key === '=') {
        e.preventDefault();
        this.adjustZoom(0.25);
        return;
      }
      if (e.key === '-' || e.key === '_') {
        e.preventDefault();
        this.adjustZoom(-0.25);
        return;
      }

      // Home & End shortcuts
      if (e.key === 'Home') {
        e.preventDefault();
        this.scrollToCorner('top-left');
        return;
      }
      if (e.key === 'End') {
        e.preventDefault();
        this.scrollToCorner('bottom-right');
        return;
      }

      // Arrow Keys Panning
      const step = e.shiftKey ? 240 : 80;
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        this.pan(0, -step);
        return;
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        this.pan(0, step);
        return;
      }
      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        this.pan(-step, 0);
        return;
      }
      if (e.key === 'ArrowRight') {
        e.preventDefault();
        this.pan(step, 0);
        return;
      }
      if (e.key === 'PageUp') {
        e.preventDefault();
        this.pan(0, -((this.viewportEl?.clientHeight || 400) * 0.8));
        return;
      }
      if (e.key === 'PageDown') {
        e.preventDefault();
        this.pan(0, (this.viewportEl?.clientHeight || 400) * 0.8);
        return;
      }

      // Focus Trap within Modal Dialog
      if (e.key === 'Tab') {
        this.trapFocus(e);
      }
    }

    trapFocus(e) {
      const focusables = this.modalEl.querySelectorAll(
        'button:not([disabled]), [tabindex]:not([tabindex="-1"]), a[href], input:not([disabled])'
      );
      if (focusables.length === 0) return;

      const first = focusables[0];
      const last = focusables[focusables.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }
  }

  return {
    MAX_ASSET_BYTES,
    MAX_DOC_MEDIA_BYTES,
    MAX_DOC_ASSET_COUNT,
    MAX_IMAGE_PIXELS,
    MAX_IMAGE_SIDE,
    ALLOWED_MIMES,
    sha256Bytes,
    decodeBase64,
    parseImageHeader,
    MediaValidator,
    MediaRenderer,
    ModalInspector
  };
});
