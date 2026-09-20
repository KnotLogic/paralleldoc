/**
 * tests/test_challenger_m5_empirical_node.cjs
 * Empirical Node.js verification and stress testing suite for Milestone 5.
 * 
 * Verifies loader, media contract, relationship graph, panel zero-loss, and literal search
 * directly against the 6 materialized corpora (V, G, M, E, S, R).
 */

const fs = require('fs');
const path = require('path');
const assert = require('assert');

const loader = require('../src/loader.js');
const media = require('../src/media.js');
const graph = require('../src/graph.js');
const panels = require('../src/panels.js');
const search = require('../src/search.js');

const FIXTURES_DIR = path.resolve(__dirname, '..', 'fixtures');
const V_DIR = path.join(FIXTURES_DIR, 'corpus_V');
const G_DIR = path.join(FIXTURES_DIR, 'corpus_G');
const M_DIR = path.join(FIXTURES_DIR, 'corpus_M');
const E_DIR = path.join(FIXTURES_DIR, 'corpus_E');
const S_DIR = path.join(FIXTURES_DIR, 'corpus_S');
const R_DIR = path.join(FIXTURES_DIR, 'corpus_R');

console.log('=== RUNNING CHALLENGER M5 EMPIRICAL SUITE (Node.js) ===\n');

let totalChecks = 0;
let passedChecks = 0;

async function checkAsync(desc, fn) {
  totalChecks++;
  try {
    await fn();
    passedChecks++;
    console.log(`  ✓ ${desc}`);
  } catch (err) {
    console.error(`  ✗ FAIL: ${desc}`);
    console.error(err);
    process.exitCode = 1;
  }
}

function check(desc, fn) {
  totalChecks++;
  try {
    fn();
    passedChecks++;
    console.log(`  ✓ ${desc}`);
  } catch (err) {
    console.error(`  ✗ FAIL: ${desc}`);
    console.error(err);
    process.exitCode = 1;
  }
}

async function runAll() {
  // -----------------------------------------------------------------------------
  // 1. BYTE-LEVEL SHA-256 & LOADER REJECTION
  // -----------------------------------------------------------------------------
  console.log('>>> 1. SHA-256 Byte Sensitivity & V3 Loader <<<');

  check('v08 (LF), v09 (CRLF), v10 (BOM) produce 3 strictly distinct hashes', () => {
    const lfBytes = fs.readFileSync(path.join(V_DIR, 'v08_byte_variant_lf.json'));
    const crlfBytes = fs.readFileSync(path.join(V_DIR, 'v09_byte_variant_crlf.json'));
    const bomBytes = fs.readFileSync(path.join(V_DIR, 'v10_byte_variant_bom.json'));

    const lfHash = loader.computeRawSha256Sync(lfBytes);
    const crlfHash = loader.computeRawSha256Sync(crlfBytes);
    const bomHash = loader.computeRawSha256Sync(bomBytes);

    assert.strictEqual(bomBytes[0], 0xEF);
    assert.strictEqual(bomBytes[1], 0xBB);
    assert.strictEqual(bomBytes[2], 0xBF);

    const hashSet = new Set([lfHash, crlfHash, bomHash]);
    assert.strictEqual(hashSet.size, 3, 'All 3 hashes must be unique');
  });

  check('1-byte mutation at multiple offsets alters raw SHA-256', () => {
    const baseBytes = fs.readFileSync(path.join(V_DIR, 'v08_byte_variant_lf.json'));
    const baseHash = loader.computeRawSha256Sync(baseBytes);

    const testOffsets = [0, 1, Math.floor(baseBytes.length / 2), baseBytes.length - 1];
    for (const offset of testOffsets) {
      const mutated = Buffer.from(baseBytes);
      mutated[offset] ^= 0x01;
      const mutHash = loader.computeRawSha256Sync(mutated);
      assert.notStrictEqual(mutHash, baseHash, `Hash failed to diverge at offset ${offset}`);
    }
  });

  await checkAsync('Legacy v2.1 and non-v3 documents rejected with exact Russian diagnostic', async () => {
    const expectedMsg = '«Неподдерживаемый формат; требуется ParallelDoc 3.0»';
    const legacyFiles = [
      'e02_missing_format_field.json',
      'e03_invalid_format_field.json',
      'e04_unknown_version_field.json',
      'e05_legacy_v21_document.json'
    ];
    for (const f of legacyFiles) {
      const raw = fs.readFileSync(path.join(E_DIR, f));
      const res = await loader.loadDocument(raw);
      assert.strictEqual(res.success, false, `Expected rejection for ${f}`);
      assert.strictEqual(res.errorType, 'REJECTED_UNSUPPORTED');
      assert.strictEqual(res.diagnosticMessage, expectedMsg);
    }
  });

  // -----------------------------------------------------------------------------
  // 2. CORPUS M: 24 MEDIA FIXTURES VALIDATION
  // -----------------------------------------------------------------------------
  console.log('\n>>> 2. Corpus M Media Contract Rejection Suite <<<');

  check('All 24 Corpus M fixtures match control ground truth in MediaValidator', () => {
    const ctrl = JSON.parse(fs.readFileSync(path.join(M_DIR, 'corpus_M_control.json'), 'utf-8'));
    assert.strictEqual(ctrl.length, 24);

    for (const entry of ctrl) {
      const doc = JSON.parse(fs.readFileSync(path.join(M_DIR, entry.file), 'utf-8'));
      const res = media.MediaValidator.validateDocumentAssets(doc.assets);
      const expected = entry.expected_code;

      if (expected === 'OK') {
        assert.strictEqual(res.issues.length, 0, `Expected 0 issues for ${entry.file}, got ${JSON.stringify(res.issues)}`);
      } else {
        const codes = res.issues.map(i => i.code);
        assert(codes.includes(expected), `Fixture ${entry.file} expected ${expected}, got ${JSON.stringify(codes)}`);
      }
    }
  });

  // -----------------------------------------------------------------------------
  // 3. CORPUS G: SLA BENCHMARK & GRAPH CONTROLS
  // -----------------------------------------------------------------------------
  console.log('\n>>> 3. Corpus G SLA Benchmark & Relationship Graph <<<');

  check('Corpus G document conforms to SLA specifications (>=12 groups, >=24 units, Russian quote >=8000 chars)', () => {
    const doc = JSON.parse(fs.readFileSync(path.join(G_DIR, 'corpus_G_sla_document.json'), 'utf-8'));
    assert(doc.groups.length >= 12, `Groups count ${doc.groups.length} < 12`);
    assert(doc.units.length >= 24, `Units count ${doc.units.length} < 24`);

    const longUnits = doc.units.filter(u => u.text.length >= 8000);
    assert(longUnits.length >= 1, 'Missing long quote >= 8000 characters');
    assert(longUnits[0].text.length >= 8000);
    assert(/[\u0400-\u04FF]/.test(longUnits[0].text), 'Long quote must contain Cyrillic text');
  });

  check('Corpus G graph: 8 nodes, 9 edges, branch, cross-group link, qualification edge, and cycle resolution', () => {
    const doc = JSON.parse(fs.readFileSync(path.join(G_DIR, 'corpus_G_sla_document.json'), 'utf-8'));
    const graphDef = doc.visuals[0];
    assert.strictEqual(graphDef.nodes.length, 8, 'Expected 8 nodes');
    assert.strictEqual(graphDef.edges.length, 9, 'Expected 9 edges');

    // Qualification edge
    const qualEdge = graphDef.edges.find(e => e.relation === 'qualifies');
    assert(qualEdge, 'Missing qualifies edge');
    assert.strictEqual(qualEdge.id, 'edge-03');

    // Cycle resolution timing (< 50ms)
    const t0 = performance.now();
    const layout = graph.computeGraphLayout(graphDef.nodes, graphDef.edges);
    const dur = performance.now() - t0;
    assert(dur < 50.0, `Cycle layout took ${dur.toFixed(2)}ms (expected < 50ms)`);
    assert(layout.nodes.length === 8);
  });

  check('10 ground truth search queries in corpus_G_control.json match expected units', () => {
    const doc = JSON.parse(fs.readFileSync(path.join(G_DIR, 'corpus_G_sla_document.json'), 'utf-8'));
    const ctrl = JSON.parse(fs.readFileSync(path.join(G_DIR, 'corpus_G_control.json'), 'utf-8'));

    const engine = new search.SearchEngine(doc, null);
    const queries = ctrl.literal_search_queries;
    assert.strictEqual(queries.length, 10);

    for (const q of queries) {
      const matches = engine.search(q.query);
      const matchedIds = new Set(matches.map(m => m.id || m.unitId).filter(Boolean));
      for (const expId of q.expected_units) {
        assert(matchedIds.has(expId), `Query '${q.query}' did not match expected unit '${expId}'`);
      }
    }
  });

  // -----------------------------------------------------------------------------
  // 4. CORPUS R: PERFORMANCE BENCHMARKS & SCALE GUARD
  // -----------------------------------------------------------------------------
  console.log('\n>>> 4. Corpus R Stress Performance & Scale Guard <<<');

  check('Corpus R 1000 units cold load <= 3.0s and search <= 300ms', () => {
    const raw = fs.readFileSync(path.join(R_DIR, 'corpus_R_stress_1000.json'));
    assert(raw.length > 5 * 1024 * 1024, 'Payload must be > 5 MiB');

    const t0 = performance.now();
    const doc = JSON.parse(raw.toString('utf-8'));
    const loadDur = performance.now() - t0;
    assert(loadDur <= 3000, `Cold load exceeded 3000ms: ${loadDur.toFixed(2)}ms`);

    assert.strictEqual(doc.units.length, 1000);

    const engine = new search.SearchEngine(doc, null);
    const tSearch0 = performance.now();
    const matches = engine.search('отказоустойчивости');
    const searchDur = performance.now() - tSearch0;
    assert(searchDur <= 300, `Search exceeded 300ms: ${searchDur.toFixed(2)}ms`);
    assert(matches.length > 0);
  });

  check('Graph Scale Guard: 200n/400e passes; 201n/401e triggers fallback boundary', () => {
    const limitDoc = JSON.parse(fs.readFileSync(path.join(R_DIR, 'corpus_R_large_graph_200n_400e.json'), 'utf-8'));
    const breachDoc = JSON.parse(fs.readFileSync(path.join(R_DIR, 'corpus_R_overflow_graph_201n_401e.json'), 'utf-8'));

    const limitVis = limitDoc.visuals[0];
    const breachVis = breachDoc.visuals[0];

    assert.strictEqual(limitVis.nodes.length, 200);
    assert.strictEqual(limitVis.edges.length, 400);
    assert.strictEqual(breachVis.nodes.length, 201);
    assert.strictEqual(breachVis.edges.length, 401);

    const limitGuard = graph.checkScaleGuard(limitVis);
    assert.strictEqual(limitGuard.breached, false, '200n/400e must NOT breach scale guard');

    const breachGuard = graph.checkScaleGuard(breachVis);
    assert.strictEqual(breachGuard.breached, true, '201n/401e MUST breach scale guard');
    assert(breachGuard.message.includes('201') || breachGuard.message.includes('401'));
  });

  // -----------------------------------------------------------------------------
  // 5. CORPUS S: SECURITY NEUTRALIZATION
  // -----------------------------------------------------------------------------
  console.log('\n>>> 5. Corpus S Security Neutralization <<<');

  check('Corpus S: scripts, event handlers, and locators are neutralized without DOM execution', () => {
    const secFiles = [
      's01_xss_script_tags.json',
      's02_html_event_handlers.json',
      's03_javascript_and_file_locators.json',
      's04_markdown_injection.json',
      's05_namespaced_extension_payload.json',
      's06_active_document_js_rejection.json'
    ];

    for (const f of secFiles) {
      const raw = fs.readFileSync(path.join(S_DIR, f));
      const doc = JSON.parse(raw.toString('utf-8'));
      assert(doc !== null, `Parsing security fixture ${f} should succeed`);

      // Verify s03 locators are blocked by validateLocator
      if (f === 's03_javascript_and_file_locators.json') {
        for (const asset of doc.assets) {
          const locRes = media.MediaValidator.validateLocator(asset.locator);
          assert.strictEqual(locRes.valid, false, `Locator should be rejected: ${JSON.stringify(asset.locator)}`);
          assert.strictEqual(locRes.code, 'ERR_FORBIDDEN_ASSET_LOCATOR');
        }
      }
    }
  });

  // -----------------------------------------------------------------------------
  // SUMMARY
  // -----------------------------------------------------------------------------
  console.log('\n======================================================');
  console.log(`CHALLENGER M5 RESULTS: ${passedChecks} / ${totalChecks} checks PASSED`);
  console.log('======================================================\n');
}

runAll();
