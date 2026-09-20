/**
 * ParallelDoc 3.0 (r2 / V3-ONLY) — Browser & Node.js Loader Engine.
 * Strict compliance with Spec r2 §7, §8, §9, §11 (F06-F09, AC-02, AC-25, AC-26, AC-28).
 *
 * Capabilities:
 * - Exact SHA-256 over raw binary bytes (preserves UTF-8 BOM, zero CRLF/LF normalization).
 * - Dual SHA-256: WebCrypto with pure JS FIPS 180-4 fallback.
 * - V3-Only Format Guard (§9): Rejects non-v3 / legacy with exact message:
 *   «Неподдерживаемый формат; требуется ParallelDoc 3.0»
 * - Safe raw text preview with line/column coordinates and visual caret pointer.
 * - Detached integrity manifest matching (manifest.schema.json, scope: "raw-bytes").
 * - Zero auto-migration, zero legacy conversion, zero silent fallback (F09).
 */

(function(root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.ParallelDocLoader = factory();
  }
})(typeof self !== 'undefined' ? self : (typeof globalThis !== 'undefined' ? globalThis : this), function() {
  'use strict';

  const REJECTION_DIAGNOSTIC_MESSAGE = "«Неподдерживаемый формат; требуется ParallelDoc 3.0»";
  const UTF8_BOM = [0xEF, 0xBB, 0xBF];
  const MAX_PREVIEW_CHARS = 5000;
  const MAX_PREVIEW_LINES = 500;

  /**
   * Pure JS FIPS 180-4 SHA-256 implementation (synchronous, 0 external dependencies).
   * @param {Uint8Array} uint8Array
   * @returns {string} 64-char lowercase hexadecimal string
   */
  function sha256Pure(uint8Array) {
    if (!(uint8Array instanceof Uint8Array)) {
      if (Array.isArray(uint8Array) || (typeof Buffer !== 'undefined' && Buffer.isBuffer(uint8Array))) {
        uint8Array = new Uint8Array(uint8Array);
      } else {
        throw new TypeError("sha256Pure requires Uint8Array");
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

        h = g;
        g = f;
        f = e;
        e = (d + temp1) | 0;
        d = c;
        c = b;
        b = a;
        a = (temp1 + temp2) | 0;
      }

      H0 = (H0 + a) | 0;
      H1 = (H1 + b) | 0;
      H2 = (H2 + c) | 0;
      H3 = (H3 + d) | 0;
      H4 = (H4 + e) | 0;
      H5 = (H5 + f) | 0;
      H6 = (H6 + g) | 0;
      H7 = (H7 + h) | 0;
    }

    const out = new Uint8Array(32);
    const outView = new DataView(out.buffer);
    outView.setInt32(0, H0, false);
    outView.setInt32(4, H1, false);
    outView.setInt32(8, H2, false);
    outView.setInt32(12, H3, false);
    outView.setInt32(16, H4, false);
    outView.setInt32(20, H5, false);
    outView.setInt32(24, H6, false);
    outView.setInt32(28, H7, false);

    return Array.from(out).map(b => b.toString(16).padStart(2, '0')).join('');
  }

  /**
   * Synchronous SHA-256 calculation.
   * @param {Uint8Array} rawBytes
   * @returns {string}
   */
  function computeRawSha256Sync(rawBytes) {
    return sha256Pure(rawBytes);
  }

  /**
   * Asynchronous SHA-256 calculation using WebCrypto with pure JS fallback.
   * @param {Uint8Array} rawBytes
   * @returns {Promise<string>}
   */
  async function computeRawSha256(rawBytes) {
    try {
      if (typeof globalThis !== 'undefined' && globalThis.crypto && globalThis.crypto.subtle && globalThis.crypto.subtle.digest) {
        const hashBuf = await globalThis.crypto.subtle.digest('SHA-256', rawBytes);
        const hashArr = Array.from(new Uint8Array(hashBuf));
        return hashArr.map(b => b.toString(16).padStart(2, '0')).join('');
      }
    } catch (err) {
      // Fall through to pure JS fallback
    }
    return sha256Pure(rawBytes);
  }

  /**
   * HTML escape helper to prevent injection in diagnostics and preview.
   * @param {string} str
   * @returns {string}
   */
  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  /**
   * Decodes raw binary bytes to string, safely stripping UTF-8 BOM if present.
   * @param {Uint8Array} rawBytes
   * @returns {string}
   */
  function decodeJsonText(rawBytes) {
    let parseBytes = rawBytes;
    if (rawBytes.length >= 3 && rawBytes[0] === 0xEF && rawBytes[1] === 0xBB && rawBytes[2] === 0xBF) {
      parseBytes = rawBytes.subarray(3);
    }
    const decoder = new TextDecoder('utf-8', { fatal: true });
    return decoder.decode(parseBytes);
  }

  /**
   * Locates 1-indexed line and column for pattern in text.
   * @param {string} rawText
   * @param {RegExp|string|null} pattern
   * @returns {{line: number, col: number}}
   */
  function locateErrorPointer(rawText, pattern) {
    if (!rawText) return { line: 1, col: 1 };
    let pos = 0;
    if (pattern) {
      const regex = typeof pattern === 'string' ? new RegExp(pattern) : pattern;
      const match = regex.exec(rawText);
      if (match) pos = match.index;
    }
    if (pos === 0 && !pattern) {
      const match = /\{/.exec(rawText);
      if (match) pos = match.index;
    }
    const lines = rawText.slice(0, pos).split('\n');
    return {
      line: lines.length,
      col: lines[lines.length - 1].length + 1
    };
  }

  /**
   * Locates line and column from a JSON.parse SyntaxError message,
   * handling standard line/column regexes, position regexes, and V8 token/context fallbacks.
   * @param {string} rawText
   * @param {string} excMessage
   * @returns {{line: number, col: number}}
   */
  function locateSyntaxError(rawText, excMessage) {
    if (!rawText) return { line: 1, col: 1 };
    const lineColMatch = excMessage.match(/line\s+(\d+)\s+column\s+(\d+)/i);
    if (lineColMatch) {
      return { line: parseInt(lineColMatch[1], 10), col: parseInt(lineColMatch[2], 10) };
    }
    const posMatch = excMessage.match(/position\s+(\d+)/i);
    if (posMatch) {
      const pos = parseInt(posMatch[1], 10);
      const lines = rawText.slice(0, pos).split('\n');
      return { line: lines.length, col: lines[lines.length - 1].length + 1 };
    }

    // Fallback for V8 messages without line/col or position (e.g. "Unexpected token 'U', ... is not valid JSON")
    const tokenMatch = excMessage.match(/Unexpected token\s+(?:'([^']+)'|([^\s,]+))/i);
    const token = tokenMatch ? (tokenMatch[1] || tokenMatch[2]) : null;

    // Try extracting context snippet from message
    const contextMatch = excMessage.match(/,\s*(.*?)\s*is not valid JSON/i);
    if (contextMatch && contextMatch[1]) {
      let clean = contextMatch[1].replace(/^[\s."]+|[\s."]+$/g, '');
      while (clean.length >= 2) {
        const idx = rawText.indexOf(clean);
        if (idx !== -1) {
          let pos = idx;
          if (token) {
            const tIdx = clean.indexOf(token);
            if (tIdx !== -1) pos += tIdx;
          }
          const lines = rawText.slice(0, pos).split('\n');
          return { line: lines.length, col: lines[lines.length - 1].length + 1 };
        }
        clean = clean.slice(1);
      }
    }

    // Scan outside string literals for the unexpected token
    if (token) {
      let inString = false;
      let escape = false;
      for (let i = 0; i < rawText.length; i++) {
        const ch = rawText[i];
        if (escape) { escape = false; continue; }
        if (ch === '\\' && inString) { escape = true; continue; }
        if (ch === '"') { inString = !inString; continue; }
        if (!inString && rawText.startsWith(token, i)) {
          const lines = rawText.slice(0, i).split('\n');
          return { line: lines.length, col: lines[lines.length - 1].length + 1 };
        }
      }
      const idx = rawText.indexOf(token);
      if (idx !== -1) {
        const lines = rawText.slice(0, idx).split('\n');
        return { line: lines.length, col: lines[lines.length - 1].length + 1 };
      }
    }

    // End of input fallback
    if (/unexpected end/i.test(excMessage)) {
      const lines = rawText.split('\n');
      return { line: lines.length, col: lines[lines.length - 1].length + 1 };
    }

    return { line: 1, col: 1 };
  }

  /**
   * Generates formatted multi-line snippet with caret indicator ^.
   * @param {string} rawText
   * @param {number} line
   * @param {number} col
   * @param {string} reason
   * @param {number} context
   * @returns {string}
   */
  function generateErrorSnippet(rawText, line, col, reason, context = 2) {
    const lines = rawText.split('\n');
    if (!lines.length) return '';
    const startIdx = Math.max(0, line - 1 - context);
    const endIdx = Math.min(lines.length, line + context);
    const out = [];
    for (let idx = startIdx; idx < endIdx; idx++) {
      const ln = idx + 1;
      const prefix = String(ln).padStart(4, ' ') + ' | ';
      out.push(prefix + lines[idx]);
      if (ln === line) {
        const spaces = ' '.repeat(prefix.length + Math.max(0, col - 1));
        out.push(spaces + '^ [ОШИБКА: ' + reason + ']');
      }
    }
    return out.join('\n');
  }

  /**
   * Produces safe raw preview object with line counts and truncation.
   * @param {Uint8Array} rawBytes
   * @param {number|null} errorLine
   * @param {number|null} errorColumn
   * @param {number} maxChars
   * @param {string|null} reason
   * @returns {object}
   */
  function generateRawPreview(rawBytes, errorLine = null, errorColumn = null, maxChars = MAX_PREVIEW_CHARS, reason = null) {
    let parseBytes = rawBytes;
    if (rawBytes.length >= 3 && rawBytes[0] === 0xEF && rawBytes[1] === 0xBB && rawBytes[2] === 0xBF) {
      parseBytes = rawBytes.subarray(3);
    }
    const nonFatalDecoder = new TextDecoder('utf-8', { fatal: false });
    const fullText = nonFatalDecoder.decode(parseBytes);
    const lines = fullText.split(/\r\n|\r|\n/);
    const totalLength = fullText.length;
    const lineCount = lines.length;
    let isTruncated = false;
    let previewText = fullText;

    if (totalLength > maxChars || lineCount > MAX_PREVIEW_LINES) {
      isTruncated = true;
      const truncatedLines = lines.slice(0, MAX_PREVIEW_LINES);
      previewText = truncatedLines.join('\n');
      if (previewText.length > maxChars) {
        previewText = previewText.slice(0, maxChars);
      }
      previewText += `\n\n... [Показаны первые ${previewText.split('\n').length} строк / ${previewText.length} символов из ${lineCount} строк / ${totalLength} символов. Полный файл сохранен]`;
    }

    let snippet = null;
    if (errorLine !== null && errorColumn !== null && errorLine >= 1 && errorLine <= lineCount) {
      snippet = generateErrorSnippet(fullText, errorLine, errorColumn, reason || 'Ошибка валидации');
    }

    return {
      text: previewText,
      totalLength,
      isTruncated,
      lineCount,
      errorLine,
      errorColumn,
      snippet
    };
  }

  /**
   * Verifies detached integrity manifest against raw bytes and metadata.
   * @param {Uint8Array} rawBytes
   * @param {object|string|Uint8Array} manifestInput
   * @param {object|null} docMetadata
   * @returns {object}
   */
  function verifyManifest(rawBytes, manifestInput, docMetadata = null) {
    const actualSha256 = sha256Pure(rawBytes);
    let manifestObj;

    if (typeof manifestInput === 'string') {
      try {
        manifestObj = JSON.parse(manifestInput);
      } catch (e) {
        return {
          isValidManifest: false,
          status: "invalid_manifest",
          message: `Синтаксическая ошибка JSON в манифесте: ${e.message}`,
          expectedSha256: null,
          actualSha256
        };
      }
    } else if (manifestInput instanceof Uint8Array || (typeof Buffer !== 'undefined' && Buffer.isBuffer(manifestInput))) {
      try {
        const text = decodeJsonText(new Uint8Array(manifestInput));
        manifestObj = JSON.parse(text);
      } catch (e) {
        return {
          isValidManifest: false,
          status: "invalid_manifest",
          message: `Синтаксическая ошибка JSON в манифесте: ${e.message}`,
          expectedSha256: null,
          actualSha256
        };
      }
    } else if (typeof manifestInput === 'object' && manifestInput !== null && !Array.isArray(manifestInput)) {
      manifestObj = manifestInput;
    } else {
      return {
        isValidManifest: false,
        status: "invalid_manifest",
        message: "Недопустимый тип входных данных манифеста",
        expectedSha256: null,
        actualSha256
      };
    }

    if (typeof manifestObj !== 'object' || manifestObj === null || Array.isArray(manifestObj)) {
      return {
        isValidManifest: false,
        status: "invalid_manifest",
        message: "Манифест должен быть JSON-объектом",
        expectedSha256: null,
        actualSha256
      };
    }

    // Enforce additionalProperties: false per manifest.schema.json
    const allowedKeys = new Set(['format', 'algorithm', 'scope', 'expected_sha256', 'document_id', 'revision']);
    const extraKeys = Object.keys(manifestObj).filter(k => !allowedKeys.has(k));
    if (extraKeys.length > 0) {
      return {
        isValidManifest: false,
        status: "invalid_manifest",
        message: `Недопустимые свойства манифеста (additionalProperties: false): ${extraKeys.join(', ')}`,
        expectedSha256: manifestObj.expected_sha256 || null,
        actualSha256
      };
    }

    // Required fields per manifest.schema.json
    if (!manifestObj.format || manifestObj.format !== 'paralleldoc-integrity-1') {
      return {
        isValidManifest: false,
        status: "invalid_manifest",
        message: `Неподдерживаемый format манифеста: ${manifestObj.format}`,
        expectedSha256: manifestObj.expected_sha256 || null,
        actualSha256
      };
    }
    if (manifestObj.scope !== 'raw-bytes') {
      return {
        isValidManifest: false,
        status: "invalid_manifest",
        message: `Неподдерживаемый scope манифеста: ${manifestObj.scope}; требуется 'raw-bytes'`,
        expectedSha256: manifestObj.expected_sha256 || null,
        actualSha256
      };
    }
    if (manifestObj.algorithm !== 'SHA-256') {
      return {
        isValidManifest: false,
        status: "invalid_manifest",
        message: `Неподдерживаемый algorithm манифеста: ${manifestObj.algorithm}; требуется 'SHA-256'`,
        expectedSha256: manifestObj.expected_sha256 || null,
        actualSha256
      };
    }
    // Expected SHA-256: strictly lowercase 64-char hex per manifest.schema.json (pattern: ^[a-f0-9]{64}$)
    if (typeof manifestObj.expected_sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(manifestObj.expected_sha256)) {
      return {
        isValidManifest: false,
        status: "invalid_manifest",
        message: "expected_sha256 должен содержать 64 строчных шестнадцатеричных символа (^[a-f0-9]{64}$)",
        expectedSha256: manifestObj.expected_sha256 || null,
        actualSha256
      };
    }

    // Optional property types per manifest.schema.json
    if ('document_id' in manifestObj && typeof manifestObj.document_id !== 'string') {
      return {
        isValidManifest: false,
        status: "invalid_manifest",
        message: "document_id должен быть строкой",
        expectedSha256: manifestObj.expected_sha256,
        actualSha256
      };
    }
    if ('revision' in manifestObj && typeof manifestObj.revision !== 'string') {
      return {
        isValidManifest: false,
        status: "invalid_manifest",
        message: "revision должна быть строкой",
        expectedSha256: manifestObj.expected_sha256,
        actualSha256
      };
    }

    // Document ID and Revision binding check
    const docId = docMetadata ? docMetadata.document_id : null;
    const docRev = docMetadata ? docMetadata.revision : null;
    const manDocId = manifestObj.document_id;
    const manRev = manifestObj.revision;

    if (manDocId !== undefined && docId !== null && manDocId !== docId) {
      return {
        isValidManifest: true,
        status: "different_document",
        message: `Манифест другого документа: заявлен '${manDocId}', активен '${docId}'`,
        expectedSha256: manifestObj.expected_sha256,
        actualSha256,
        manifestDocId: manDocId,
        docId
      };
    }

    if (manRev !== undefined && docRev !== null && manRev !== docRev) {
      return {
        isValidManifest: true,
        status: "different_document",
        message: `Манифест другой ревизии: заявлена '${manRev}', активна '${docRev}'`,
        expectedSha256: manifestObj.expected_sha256,
        actualSha256,
        manifestRevision: manRev,
        docRevision: docRev
      };
    }

    const expected = manifestObj.expected_sha256;
    const actual = actualSha256;

    if (expected === actual) {
      return {
        isValidManifest: true,
        status: "matched",
        message: "Хэш совпадает с эталоном",
        expectedSha256: expected,
        actualSha256: actual,
        scope: "raw-bytes"
      };
    } else {
      return {
        isValidManifest: true,
        status: "mismatch",
        message: "SHA mismatch документа: Другая версия или изменение",
        expectedSha256: expected,
        actualSha256: actual,
        scope: "raw-bytes"
      };
    }
  }

  /**
   * Master document loader.
   * @param {Uint8Array} rawBytes
   * @param {object|string|Uint8Array|null} manifestInput
   * @param {string|null} expectedSha256
   * @returns {Promise<object>} DocumentLoadResult
   */
  async function loadDocument(rawBytes, manifestInput = null, expectedSha256 = null) {
    if (!(rawBytes instanceof Uint8Array)) {
      if (typeof Buffer !== 'undefined' && Buffer.isBuffer(rawBytes)) {
        rawBytes = new Uint8Array(rawBytes);
      } else {
        return {
          success: false,
          errorType: "REJECTED_UNSUPPORTED",
          diagnosticMessage: REJECTION_DIAGNOSTIC_MESSAGE,
          rawSha256: "",
          hasBom: false,
          byteLength: 0,
          structureState: "invalid",
          integrityState: "unavailable",
          doc: null,
          issues: [{ path: "", message: "Ожидались бинарные байты", severity: "error", code: "ERR_INVALID_TYPE" }],
          rawPreview: null,
          manifestResult: null,
          stats: {}
        };
      }
    }

    const byteLength = rawBytes.length;
    const hasBom = byteLength >= 3 && rawBytes[0] === 0xEF && rawBytes[1] === 0xBB && rawBytes[2] === 0xBF;
    const rawSha256 = await computeRawSha256(rawBytes);

    if (byteLength === 0) {
      const preview = {
        text: "",
        totalLength: 0,
        isTruncated: false,
        lineCount: 0,
        errorLine: 1,
        errorColumn: 1,
        snippet: null
      };
      return {
        success: false,
        errorType: "EMPTY_INPUT",
        diagnosticMessage: REJECTION_DIAGNOSTIC_MESSAGE,
        rawSha256,
        hasBom: false,
        byteLength: 0,
        structureState: "invalid",
        integrityState: "computed",
        doc: null,
        issues: [{ path: "", message: "Файл пуст", severity: "error", code: "ERR_EMPTY_FILE", line: 1, column: 1 }],
        rawPreview: preview,
        manifestResult: null,
        stats: {},
        rawText: "",
        line: 1,
        column: 1
      };
    }

    // Stage 0: UTF-8 Decode (BOM stripped ONLY for text decoding)
    let rawText;
    try {
      rawText = decodeJsonText(rawBytes);
    } catch (exc) {
      const preview = generateRawPreview(rawBytes, 1, 1, MAX_PREVIEW_CHARS, `Ошибка UTF-8: ${exc.message}`);
      return {
        success: false,
        errorType: "UTF8_DECODE_ERROR",
        diagnosticMessage: `Ошибка декодирования UTF-8: ${exc.message}`,
        rawSha256,
        hasBom,
        byteLength,
        structureState: "invalid",
        integrityState: "computed",
        doc: null,
        issues: [{ path: "", message: `Ошибка декодирования UTF-8: ${exc.message}`, severity: "error", code: "ERR_UTF8_DECODE", line: 1, column: 1, snippet: preview.snippet }],
        rawPreview: preview,
        manifestResult: null,
        stats: {},
        rawText: null,
        line: 1,
        column: 1,
        snippet: preview.snippet
      };
    }

    // Stage 1: JSON Parsing
    let data;
    try {
      data = JSON.parse(rawText);
    } catch (exc) {
      const loc = locateSyntaxError(rawText, exc.message);
      const line = loc.line;
      const col = loc.col;
      const preview = generateRawPreview(rawBytes, line, col, MAX_PREVIEW_CHARS, `Синтаксическая ошибка: ${exc.message}`);
      return {
        success: false,
        errorType: "PARSE_ERROR",
        diagnosticMessage: `Синтаксическая ошибка JSON: ${exc.message} (строка ${line}, колонка ${col})`,
        rawSha256,
        hasBom,
        byteLength,
        structureState: "invalid",
        integrityState: "computed",
        doc: null,
        issues: [{ path: "", message: `Синтаксическая ошибка JSON: ${exc.message}`, severity: "error", code: "ERR_JSON_PARSE", line, column: col, snippet: preview.snippet }],
        rawPreview: preview,
        manifestResult: null,
        stats: {},
        rawText,
        line,
        column: col,
        snippet: preview.snippet
      };
    }

    // Stage 2: Non-object root
    if (typeof data !== 'object' || data === null || Array.isArray(data)) {
      const preview = generateRawPreview(rawBytes, 1, 1, MAX_PREVIEW_CHARS, "Корень документа должен быть JSON-объектом");
      return {
        success: false,
        errorType: "REJECTED_UNSUPPORTED",
        diagnosticMessage: REJECTION_DIAGNOSTIC_MESSAGE,
        rawSha256,
        hasBom,
        byteLength,
        structureState: "invalid",
        integrityState: "computed",
        doc: null,
        issues: [{ path: "", message: REJECTION_DIAGNOSTIC_MESSAGE, severity: "error", code: "ERR_REJECTED_UNSUPPORTED", line: 1, column: 1, snippet: preview.snippet }],
        rawPreview: preview,
        manifestResult: null,
        stats: {},
        rawText,
        line: 1,
        column: 1,
        snippet: preview.snippet
      };
    }

    // Stage 3: Strict V3-Only Format Guard (§9)
    const isLegacy = ('columns' in data) || ('items' in data);
    const formatVal = data.format;
    const versionVal = data.version;

    if (isLegacy || formatVal !== 'paralleldoc' || versionVal !== '3.0') {
      let pattern = /\{/;
      let reason = "Неподдерживаемый формат";
      if (isLegacy) {
        pattern = /"(?:columns|items)"\s*:/;
        reason = "Обнаружены устаревшие поля v2.1 (columns/items)";
      } else if (formatVal !== 'paralleldoc') {
        pattern = /"format"\s*:/;
        reason = `Неверный или отсутствующий формат: ${formatVal}`;
      } else {
        pattern = /"version"\s*:/;
        reason = `Неверная или отсутствующая версия: ${versionVal}`;
      }

      const loc = locateErrorPointer(rawText, pattern);
      const preview = generateRawPreview(rawBytes, loc.line, loc.col, MAX_PREVIEW_CHARS, reason);
      return {
        success: false,
        errorType: "REJECTED_UNSUPPORTED",
        diagnosticMessage: REJECTION_DIAGNOSTIC_MESSAGE,
        rawSha256,
        hasBom,
        byteLength,
        structureState: "invalid",
        integrityState: "computed",
        doc: null, // Absolute prohibition of auto-migration or fallback (F09)
        issues: [{ path: "", message: REJECTION_DIAGNOSTIC_MESSAGE, severity: "error", code: "ERR_REJECTED_UNSUPPORTED", line: loc.line, column: loc.col, snippet: preview.snippet }],
        rawPreview: preview,
        manifestResult: null,
        stats: {},
        rawText,
        line: loc.line,
        column: loc.col,
        snippet: preview.snippet
      };
    }

    // Stage 4: Basic V3 Schema Check for Required Collections
    const requiredCollections = ['metadata', 'authors', 'units', 'groups', 'visuals', 'assets', 'profiles'];
    const missingCollections = requiredCollections.filter(c => !(c in data));
    let structureState = "valid";
    let errorType = "NONE";
    let diagnosticMessage = null;
    const issues = [];

    if (missingCollections.length > 0) {
      structureState = "invalid";
      errorType = "SCHEMA_VIOLATION";
      diagnosticMessage = "Ошибка валидации схемы Draft 2020-12 (schema.v3.json)";
      for (const mc of missingCollections) {
        issues.push({
          path: `/${mc}`,
          message: `Отсутствует обязательная коллекция: ${mc}`,
          severity: "error",
          code: "ERR_SCHEMA_V3_VIOLATION"
        });
      }
    }

    // Stage 5: Integrity State & Manifest Evaluation
    let integrityState = "computed";
    let manifestResult = null;

    if (manifestInput !== null) {
      manifestResult = verifyManifest(rawBytes, manifestInput, data.metadata || null);
      if (manifestResult.status === 'matched') {
        integrityState = "matched";
      } else if (manifestResult.status === 'mismatch') {
        integrityState = "mismatch";
      } else {
        integrityState = "computed";
      }
    } else if (expectedSha256 !== null) {
      if (expectedSha256.toLowerCase() === rawSha256.toLowerCase()) {
        integrityState = "matched";
      } else {
        integrityState = "mismatch";
      }
    }

    const preview = generateRawPreview(rawBytes);

    const trustStates = {
      structure: structureState,
      integrity: integrityState,
      workflow: (data && data.metadata && data.metadata.workflow_status) || 'draft'
    };

    return {
      success: structureState === "valid",
      errorType,
      diagnosticMessage,
      rawSha256,
      hasBom,
      byteLength,
      structureState,
      integrityState,
      trustStates,
      doc: data,
      issues,
      rawPreview: preview,
      manifestResult,
      stats: {
        units_count: Array.isArray(data.units) ? data.units.length : 0,
        groups_count: Array.isArray(data.groups) ? data.groups.length : 0,
        visuals_count: Array.isArray(data.visuals) ? data.visuals.length : 0,
        assets_count: Array.isArray(data.assets) ? data.assets.length : 0
      },
      rawText
    };
  }

  /**
   * Safe DOM renderer for rejected documents.
   * Conforms strictly to AC-42 (0 script execution, safe textContent, no innerHTML injection).
   * @param {object} result DocumentLoadResult
   * @param {HTMLElement} containerEl
   * @param {string} filename
   */
  function renderRejectionView(result, containerEl, filename = 'document.json') {
    if (!containerEl) return;
    while (containerEl.firstChild) {
      containerEl.removeChild(containerEl.firstChild);
    }

    const wrap = document.createElement('div');
    wrap.className = 'pd-rejection-view';
    wrap.setAttribute('role', 'alert');

    // Header Card
    const header = document.createElement('div');
    header.className = 'pd-rejection-header';

    const title = document.createElement('h2');
    title.className = 'pd-rejection-title';
    title.textContent = result.diagnosticMessage || REJECTION_DIAGNOSTIC_MESSAGE;
    header.appendChild(title);

    const meta = document.createElement('div');
    meta.className = 'pd-rejection-meta';

    const fileSpan = document.createElement('span');
    fileSpan.appendChild(document.createTextNode('Файл: '));
    const fileStrong = document.createElement('strong');
    fileStrong.textContent = filename;
    fileSpan.appendChild(fileStrong);
    meta.appendChild(fileSpan);

    const shaSpan = document.createElement('span');
    shaSpan.appendChild(document.createTextNode('SHA-256: '));
    const shaCode = document.createElement('code');
    shaCode.className = 'pd-sha-badge';
    shaCode.textContent = result.rawSha256 || 'Не вычислен';
    shaSpan.appendChild(shaCode);
    meta.appendChild(shaSpan);

    if (result.line || (result.rawPreview && result.rawPreview.errorLine)) {
      const coordSpan = document.createElement('span');
      const lineNum = result.line || result.rawPreview.errorLine;
      const colNum = result.column || result.rawPreview.errorColumn || 1;
      coordSpan.textContent = `Координаты: Строка ${lineNum}, Колонка ${colNum}`;
      meta.appendChild(coordSpan);
    }

    header.appendChild(meta);
    wrap.appendChild(header);

    // Snippet with Pointer Caret
    const snippetText = result.snippet || (result.rawPreview && result.rawPreview.snippet);
    if (snippetText) {
      const snippetSec = document.createElement('div');
      snippetSec.className = 'pd-snippet-section';

      const snippetLabel = document.createElement('div');
      snippetLabel.className = 'pd-section-label';
      snippetLabel.textContent = 'Указатель ошибки:';
      snippetSec.appendChild(snippetLabel);

      const snippetPre = document.createElement('pre');
      snippetPre.className = 'pd-snippet-pre';
      snippetPre.textContent = snippetText;
      snippetSec.appendChild(snippetPre);
      wrap.appendChild(snippetSec);
    }

    // Safe Raw Text Preview
    const rawPreviewObj = result.rawPreview;
    if (rawPreviewObj && rawPreviewObj.text) {
      const rawSec = document.createElement('div');
      rawSec.className = 'pd-raw-section';

      const rawLabel = document.createElement('div');
      rawLabel.className = 'pd-section-label';
      rawLabel.textContent = 'Исходный текст файла (безопасный предпросмотр):';
      rawSec.appendChild(rawLabel);

      const rawPre = document.createElement('pre');
      rawPre.className = 'pd-raw-pre';
      rawPre.textContent = rawPreviewObj.text;
      rawSec.appendChild(rawPre);
      wrap.appendChild(rawSec);
    }

    containerEl.appendChild(wrap);
  }

  return {
    REJECTION_DIAGNOSTIC_MESSAGE,
    UTF8_BOM,
    MAX_PREVIEW_CHARS,
    MAX_PREVIEW_LINES,
    sha256Pure,
    computeRawSha256Sync,
    computeRawSha256,
    escapeHtml,
    decodeJsonText,
    locateErrorPointer,
    locateSyntaxError,
    generateErrorSnippet,
    generateRawPreview,
    verifyManifest,
    loadDocument,
    renderRejectionView
  };
});
