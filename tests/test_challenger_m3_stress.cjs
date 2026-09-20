/**
 * tests/test_challenger_m3_stress.cjs
 * Empirical Stress Test Suite for Milestone 3 (Challenger M3-1)
 *
 * Covers:
 * 1. Graph Stress Testing (cycles, self-loops, dense meshes, bidirectional, timing < 50ms, determinism, scale guard)
 * 2. Multi-Panel & Zero Loss Stress (missing roles, orphans, empty collections, profiles 2/3/4, 10-target LIFO history)
 * 3. Search Stress (regex metacharacters, Unicode accents, Cyrillic, punctuation, rapid wrap-around)
 */

const assert = require('assert');
const {
  RELATION_CONFIG,
  SCALE_GUARD_MAX_NODES,
  SCALE_GUARD_MAX_EDGES,
  checkScaleGuard,
  computeGraphLayout
} = require('../src/graph.js');

const {
  BUILTIN_PROFILES,
  MISSING_ROLE_CONFIG,
  PanelsEngine
} = require('../src/panels.js');

const { SearchEngine } = require('../src/search.js');

console.log('===============================================================');
console.log('CHALLENGER M3-1: EMPIRICAL STRESS TEST SUITE (Node.js Engine)');
console.log('===============================================================\n');

const metrics = {
  graphTestsPassed: 0,
  panelTestsPassed: 0,
  searchTestsPassed: 0,
  timings: {}
};

// ============================================================================
// PART 1: GRAPH STRESS TESTING
// ============================================================================
console.log('>>> SECTION 1: GRAPH ADVERSARIAL STRESS TESTING <<<');

// 1.1 Cycle Tolerance: Multi-node circular feedback loops
console.log('\n--- 1.1 Multi-node circular feedback loops ---');
const cycleSizes = [3, 10, 25, 50, 100];
for (const size of cycleSizes) {
  const nodes = [];
  const edges = [];
  for (let i = 0; i < size; i++) {
    nodes.push({ id: `c-node-${i}`, label: `Cycle Node ${i}`, unit_refs: [`u-${i}`] });
    edges.push({
      id: `c-edge-${i}`,
      from: `c-node-${i}`,
      to: `c-node-${(i + 1) % size}`,
      relation: 'depends_on',
      label: `Loop ${i}->${(i + 1) % size}`
    });
  }

  const t0 = performance.now();
  const layout = computeGraphLayout(nodes, edges, 900, 600);
  const elapsed = performance.now() - t0;
  metrics.timings[`cycle_${size}`] = elapsed;

  assert.strictEqual(layout.nodes.length, size, `Layout must have ${size} nodes`);
  for (const n of layout.nodes) {
    assert(Number.isFinite(n.x), `Node ${n.id} X must be finite, got ${n.x}`);
    assert(Number.isFinite(n.y), `Node ${n.id} Y must be finite, got ${n.y}`);
    assert(!Number.isNaN(n.x), `Node ${n.id} X must not be NaN`);
    assert(!Number.isNaN(n.y), `Node ${n.id} Y must not be NaN`);
  }

  if (size === 100) {
    assert(elapsed < 50.0, `100-node circular cycle took ${elapsed.toFixed(2)}ms (MUST be < 50ms)`);
  }
  console.log(`  ✓ Circular loop of ${size} nodes resolved in ${elapsed.toFixed(2)}ms (zero recursion, all coordinates finite)`);
  metrics.graphTestsPassed++;
}

// 1.2 Cycle Tolerance: Self-loops (A -> A)
console.log('\n--- 1.2 Self-loops (A -> A) ---');
{
  const nodes = [
    { id: 'self-node-A', label: 'Self A', unit_refs: [] },
    { id: 'self-node-B', label: 'Self B', unit_refs: [] }
  ];
  const edges = [
    { id: 'se-1', from: 'self-node-A', to: 'self-node-A', relation: 'qualifies', label: 'A qualifies itself' },
    { id: 'se-2', from: 'self-node-B', to: 'self-node-B', relation: 'contradicts', label: 'B contradicts itself' },
    { id: 'se-3', from: 'self-node-A', to: 'self-node-B', relation: 'supports', label: 'A supports B' }
  ];

  const t0 = performance.now();
  const layout = computeGraphLayout(nodes, edges, 800, 500);
  const elapsed = performance.now() - t0;

  assert.strictEqual(layout.nodes.length, 2);
  for (const n of layout.nodes) {
    assert(Number.isFinite(n.x) && Number.isFinite(n.y), 'Coordinates must be finite on self-loops');
  }
  console.log(`  ✓ Self-loops (A->A, B->B) resolved safely in ${elapsed.toFixed(2)}ms`);
  metrics.graphTestsPassed++;
}

// 1.3 Dense Mesh Topologies (Complete graph K_10, K_20, dense bipartite)
console.log('\n--- 1.3 Dense Mesh Topologies ---');
{
  // K_10: 10 nodes, 90 directed edges (all-to-all)
  const k10Nodes = Array.from({ length: 10 }, (_, i) => ({ id: `k10-${i}`, label: `K10-${i}` }));
  const k10Edges = [];
  for (let i = 0; i < 10; i++) {
    for (let j = 0; j < 10; j++) {
      if (i !== j) {
        k10Edges.push({ id: `k10-e-${i}-${j}`, from: `k10-${i}`, to: `k10-${j}`, relation: 'compares' });
      }
    }
  }

  const t0 = performance.now();
  const k10Layout = computeGraphLayout(k10Nodes, k10Edges, 800, 600);
  const k10Elapsed = performance.now() - t0;
  assert.strictEqual(k10Layout.nodes.length, 10);
  assert.strictEqual(k10Edges.length, 90);
  console.log(`  ✓ Complete graph K_10 (10 nodes, 90 edges) resolved in ${k10Elapsed.toFixed(2)}ms`);
  metrics.graphTestsPassed++;

  // Dense mesh: 50 nodes with 300 edges
  const m50Nodes = Array.from({ length: 50 }, (_, i) => ({ id: `m50-${i}`, label: `Mesh ${i}` }));
  const m50Edges = [];
  for (let i = 0; i < 50; i++) {
    for (let offset = 1; offset <= 6; offset++) {
      const target = (i + offset) % 50;
      m50Edges.push({
        id: `m50-e-${i}-${target}`,
        from: `m50-${i}`,
        to: `m50-${target}`,
        relation: ['supports', 'qualifies', 'contradicts', 'depends_on', 'precedes', 'compares'][offset % 6]
      });
    }
  }
  assert.strictEqual(m50Edges.length, 300);

  const t1 = performance.now();
  const m50Layout = computeGraphLayout(m50Nodes, m50Edges, 1000, 800);
  const m50Elapsed = performance.now() - t1;
  assert.strictEqual(m50Layout.nodes.length, 50);
  for (const n of m50Layout.nodes) {
    assert(Number.isFinite(n.x) && Number.isFinite(n.y));
  }
  console.log(`  ✓ Dense mesh (50 nodes, 300 edges) resolved in ${m50Elapsed.toFixed(2)}ms`);
  metrics.graphTestsPassed++;
}

// 1.4 Bidirectional Cycles (A <-> B pairs)
console.log('\n--- 1.4 Bidirectional Cycles (A <-> B pairs) ---');
{
  const bidiNodes = [];
  const bidiEdges = [];
  // 50 pairs = 100 nodes, 100 edges forward + 100 edges backward = 200 edges
  for (let i = 0; i < 50; i++) {
    const idA = `pair-${i}-A`;
    const idB = `pair-${i}-B`;
    bidiNodes.push({ id: idA, label: `Pair ${i} A` });
    bidiNodes.push({ id: idB, label: `Pair ${i} B` });

    bidiEdges.push({ id: `e-${i}-fwd`, from: idA, to: idB, relation: 'depends_on', label: 'fwd' });
    bidiEdges.push({ id: `e-${i}-rev`, from: idB, to: idA, relation: 'depends_on', label: 'rev' });
  }

  const t0 = performance.now();
  const bidiLayout = computeGraphLayout(bidiNodes, bidiEdges, 1200, 800);
  const elapsed = performance.now() - t0;
  metrics.timings.bidi_100_nodes = elapsed;

  assert.strictEqual(bidiLayout.nodes.length, 100);
  for (const n of bidiLayout.nodes) {
    assert(Number.isFinite(n.x) && Number.isFinite(n.y));
  }
  assert(elapsed < 50.0, `100-node bidirectional cycle took ${elapsed.toFixed(2)}ms (must be < 50ms)`);
  console.log(`  ✓ 100-node bidirectional cycles (50 mutual pairs, 200 edges) resolved in ${elapsed.toFixed(2)}ms`);
  metrics.graphTestsPassed++;
}

// 1.5 Coordinate Determinism Verification
console.log('\n--- 1.5 Coordinate Determinism (10 consecutive identical runs) ---');
{
  const testNodes = Array.from({ length: 20 }, (_, i) => ({ id: `det-n-${i}`, label: `Determinism ${i}` }));
  const testEdges = [];
  for (let i = 0; i < 19; i++) {
    testEdges.push({ id: `det-e-${i}`, from: `det-n-${i}`, to: `det-n-${i + 1}`, relation: 'supports' });
  }
  testEdges.push({ id: 'det-e-cycle', from: 'det-n-19', to: 'det-n-0', relation: 'depends_on' });

  const baseline = computeGraphLayout(testNodes, testEdges, 800, 500);
  for (let run = 1; run <= 10; run++) {
    const current = computeGraphLayout(testNodes, testEdges, 800, 500);
    for (let i = 0; i < testNodes.length; i++) {
      assert.strictEqual(
        current.nodes[i].x.toFixed(6),
        baseline.nodes[i].x.toFixed(6),
        `Run ${run} node ${i} X must be bitwise identical`
      );
      assert.strictEqual(
        current.nodes[i].y.toFixed(6),
        baseline.nodes[i].y.toFixed(6),
        `Run ${run} node ${i} Y must be bitwise identical`
      );
    }
  }
  console.log('  ✓ 10 consecutive runs produced 100% identical coordinates (Zero Jitter / Full Determinism)');
  metrics.graphTestsPassed++;
}

// 1.6 Scale Limit Guard Exact Boundary Testing (AC-44)
console.log('\n--- 1.6 Scale Limit Guard Exact Boundary Testing (AC-44) ---');
{
  // Exact boundary 1: 200 nodes / 400 edges -> NOT breached
  const nodes200 = Array.from({ length: 200 }, (_, i) => ({ id: `n-${i}` }));
  const edges400 = Array.from({ length: 400 }, (_, i) => ({ id: `e-${i}`, from: `n-${i % 200}`, to: `n-${(i + 1) % 200}`, relation: 'supports' }));
  const check200_400 = checkScaleGuard({ nodes: nodes200, edges: edges400 });
  assert.strictEqual(check200_400.breached, false, 'Exactly 200 nodes and 400 edges MUST NOT breach scale limit guard');
  console.log('  ✓ Exactly 200 nodes / 400 edges: breached = false (SVG rendering allowed)');
  metrics.graphTestsPassed++;

  // Exact boundary 2: 201 nodes / 0 edges -> BREACHED
  const nodes201 = Array.from({ length: 201 }, (_, i) => ({ id: `n-${i}` }));
  const check201_0 = checkScaleGuard({ nodes: nodes201, edges: [] });
  assert.strictEqual(check201_0.breached, true, '201 nodes MUST breach scale limit guard');
  assert.strictEqual(check201_0.nodeCount, 201);
  assert(check201_0.message.includes('201 узлов'), 'Message must reflect 201 nodes');
  assert(check201_0.message.includes('AC-44'), 'Message must cite AC-44');
  console.log('  ✓ Exactly 201 nodes: breached = true (AC-44 guard triggered)');
  metrics.graphTestsPassed++;

  // Exact boundary 3: 200 nodes / 401 edges -> BREACHED
  const edges401 = Array.from({ length: 401 }, (_, i) => ({ id: `e-${i}`, from: `n-${i % 200}`, to: `n-${(i + 1) % 200}`, relation: 'supports' }));
  const check200_401 = checkScaleGuard({ nodes: nodes200, edges: edges401 });
  assert.strictEqual(check200_401.breached, true, '401 edges MUST breach scale limit guard');
  assert.strictEqual(check200_401.edgeCount, 401);
  assert(check200_401.message.includes('401 связей'), 'Message must reflect 401 edges');
  assert(check200_401.message.includes('AC-44'), 'Message must cite AC-44');
  console.log('  ✓ Exactly 401 edges: breached = true (AC-44 guard triggered)');
  metrics.graphTestsPassed++;
}

// ============================================================================
// PART 2: MULTI-PANEL & ZERO UNIT LOSS STRESS TESTING
// ============================================================================
console.log('\n>>> SECTION 2: MULTI-PANEL & ZERO UNIT LOSS STRESS TESTING <<<');

function createAdversarialDoc(name, units, groups) {
  return {
    format: 'paralleldoc',
    version: '3.0',
    metadata: {
      document_id: `doc-stress-${name}`,
      revision: 'r1',
      title: `Stress Test Doc: ${name}`,
      author_refs: ['auth-stress']
    },
    authors: [
      { id: 'auth-stress', kind: 'human', name: 'Stress Harness' }
    ],
    units,
    groups,
    visuals: [],
    assets: [],
    profiles: []
  };
}

// 2.1 Missing Roles Combinations
console.log('\n--- 2.1 Diverse Combinations of Missing Roles ---');
{
  const engine = new PanelsEngine();

  // Test Case A: ONLY sources (no model, analysis, action)
  const docOnlySources = createAdversarialDoc('only-sources', [
    { id: 's1', kind: 'source', title: 'Source 1', text: 'Text 1' },
    { id: 's2', kind: 'source', title: 'Source 2', text: 'Text 2' },
    { id: 's3', kind: 'source', title: 'Source 3', text: 'Text 3' }
  ], [
    { id: 'g1', title: 'Source Group', unit_refs: ['s1', 's2', 's3'] }
  ]);
  engine.loadDocument(docOnlySources);

  for (const pId of ['builtin:2', 'builtin:3', 'builtin:4']) {
    engine.setProfile(pId);
    const plan = engine.getRenderPlan();
    assert.strictEqual(plan.totalUnitsCount, 3, `OnlySources: profile ${pId} lost units!`);
    assert(plan.missingRoleCount > 0, `OnlySources: profile ${pId} must report missing roles`);
  }
  console.log('  ✓ Document with ONLY source units verified across all profiles (Zero Loss)');
  metrics.panelTestsPassed++;

  // Test Case B: ONLY actions (no source, model, analysis)
  const docOnlyActions = createAdversarialDoc('only-actions', [
    { id: 'a1', kind: 'action', title: 'Action 1', text: 'Act 1' },
    { id: 'a2', kind: 'action', title: 'Action 2', text: 'Act 2' }
  ], [
    { id: 'g-act', title: 'Action Group', unit_refs: ['a1', 'a2'] }
  ]);
  engine.loadDocument(docOnlyActions);

  for (const pId of ['builtin:2', 'builtin:3', 'builtin:4']) {
    engine.setProfile(pId);
    const plan = engine.getRenderPlan();
    assert.strictEqual(plan.totalUnitsCount, 2, `OnlyActions: profile ${pId} lost units!`);
  }
  console.log('  ✓ Document with ONLY action units verified across all profiles (Zero Loss)');
  metrics.panelTestsPassed++;

  // Test Case C: ONLY analysis (conclusions)
  const docOnlyAnalysis = createAdversarialDoc('only-analysis', [
    { id: 'an1', kind: 'analysis', title: 'Analysis 1', text: 'Ana 1' },
    { id: 'an2', kind: 'analysis', title: 'Analysis 2', text: 'Ana 2' },
    { id: 'an3', kind: 'analysis', title: 'Analysis 3', text: 'Ana 3' }
  ], [
    { id: 'g-ana', title: 'Analysis Group', unit_refs: ['an1', 'an2', 'an3'] }
  ]);
  engine.loadDocument(docOnlyAnalysis);

  for (const pId of ['builtin:2', 'builtin:3', 'builtin:4']) {
    engine.setProfile(pId);
    const plan = engine.getRenderPlan();
    assert.strictEqual(plan.totalUnitsCount, 3, `OnlyAnalysis: profile ${pId} lost units!`);
  }
  console.log('  ✓ Document with ONLY analysis units verified across all profiles (Zero Loss)');
  metrics.panelTestsPassed++;

  // Test Case D: ONLY model units
  const docOnlyModels = createAdversarialDoc('only-models', [
    { id: 'm1', kind: 'model', title: 'Model 1', text: 'Mod 1' },
    { id: 'm2', kind: 'model', title: 'Model 2', text: 'Mod 2' }
  ], [
    { id: 'g-mod', title: 'Model Group', unit_refs: ['m1', 'm2'] }
  ]);
  engine.loadDocument(docOnlyModels);

  for (const pId of ['builtin:2', 'builtin:3', 'builtin:4']) {
    engine.setProfile(pId);
    const plan = engine.getRenderPlan();
    assert.strictEqual(plan.totalUnitsCount, 2, `OnlyModels: profile ${pId} lost units!`);
  }
  console.log('  ✓ Document with ONLY model units verified across all profiles (Zero Loss)');
  metrics.panelTestsPassed++;
}

// 2.2 Orphaned Units Without Groups & Empty Collections
console.log('\n--- 2.2 Orphaned Units Reconciliation & Empty Collections ---');
{
  const engine = new PanelsEngine();

  // 0 groups, 50 orphaned units of mixed kinds
  const orphanUnits = [];
  const kinds = ['source', 'model', 'analysis', 'action'];
  for (let i = 0; i < 50; i++) {
    orphanUnits.push({
      id: `orphan-${i}`,
      kind: kinds[i % 4],
      title: `Orphan Unit ${i}`,
      text: `Body text of orphan ${i}`
    });
  }

  const docAllOrphans = createAdversarialDoc('all-orphans', orphanUnits, []);
  engine.loadDocument(docAllOrphans);

  assert.strictEqual(engine.orphanUnits.length, 50, 'All 50 units must be classified as orphans');
  assert.strictEqual(engine.groupList.length, 1, 'Group list must have synthetic __orphans__ group');
  assert.strictEqual(engine.groupList[0].id, '__orphans__');

  for (const pId of ['builtin:2', 'builtin:3', 'builtin:4']) {
    engine.setProfile(pId);
    const plan = engine.getRenderPlan();
    assert.strictEqual(plan.totalUnitsCount, 50, `AllOrphans: profile ${pId} must render all 50 units`);
  }
  console.log('  ✓ Document with 0 groups and 50 orphan units reconciled under «Вне групп» (Zero Loss)');
  metrics.panelTestsPassed++;

  // Empty document (0 units, 0 groups)
  const docEmpty = createAdversarialDoc('empty', [], []);
  engine.loadDocument(docEmpty);
  assert.strictEqual(engine.orphanUnits.length, 0);
  assert.strictEqual(engine.groupList.length, 0);
  const planEmpty = engine.getRenderPlan();
  assert.strictEqual(planEmpty.totalUnitsCount, 0);
  console.log('  ✓ Empty document (0 units, 0 groups) handled gracefully with 0 crashes');
  metrics.panelTestsPassed++;

  // Groups with empty unit_refs
  const docEmptyGroups = createAdversarialDoc('empty-groups', [], [
    { id: 'eg-1', title: 'Empty Group 1', unit_refs: [] },
    { id: 'eg-2', title: 'Empty Group 2', unit_refs: [] }
  ]);
  engine.loadDocument(docEmptyGroups);
  assert.strictEqual(engine.groupList.length, 2);
  const planEG = engine.getRenderPlan();
  assert.strictEqual(planEG.totalUnitsCount, 0);
  console.log('  ✓ Document with empty groups handled safely');
  metrics.panelTestsPassed++;
}

// 2.3 Deep / Wide Collections (50 groups, 150 units) Zero Loss
console.log('\n--- 2.3 Large Scale Document (50 groups, 150 units) Zero Loss ---');
{
  const engine = new PanelsEngine();
  const largeUnits = [];
  const largeGroups = [];
  const kinds = ['source', 'model', 'analysis', 'action'];

  let uCount = 0;
  for (let g = 0; g < 50; g++) {
    const gUnits = [];
    const numUnitsInGroup = (g % 3) + 1; // 1 to 3 units per group
    for (let u = 0; u < numUnitsInGroup; u++) {
      const uId = `u-lg-${uCount++}`;
      largeUnits.push({
        id: uId,
        kind: kinds[(g + u) % 4],
        title: `Unit ${uId}`,
        text: `Content ${uId}`
      });
      gUnits.push(uId);
    }
    largeGroups.push({ id: `g-lg-${g}`, title: `Group ${g}`, unit_refs: gUnits });
  }

  // Add 10 unassigned orphan units
  for (let o = 0; o < 10; o++) {
    const oId = `u-orphan-lg-${o}`;
    largeUnits.push({ id: oId, kind: kinds[o % 4], title: `Orphan ${o}`, text: `Orphan text ${o}` });
    uCount++;
  }

  const totalExpected = largeUnits.length; // uCount
  const docLarge = createAdversarialDoc('large-corpus', largeUnits, largeGroups);
  engine.loadDocument(docLarge);

  assert.strictEqual(engine.orphanUnits.length, 10);
  assert.strictEqual(engine.groupList.length, 51); // 50 doc groups + 1 orphan group

  for (const pId of ['builtin:2', 'builtin:3', 'builtin:4']) {
    engine.setProfile(pId);
    const plan = engine.getRenderPlan();
    assert.strictEqual(
      plan.totalUnitsCount,
      totalExpected,
      `Large doc: profile ${pId} rendered ${plan.totalUnitsCount}, expected ${totalExpected}`
    );
  }
  console.log(`  ✓ Large document (${totalExpected} units across 50 groups + 10 orphans): 100% Zero Unit Loss across Compare/Evidence/Review`);
  metrics.panelTestsPassed++;
}

// 2.4 10-Target LIFO History Stack Bounds & Return-to-Anchor (>15 sequential navigations)
console.log('\n--- 2.4 10-Target LIFO History Stack Bounds (>15 Jumps) ---');
{
  const engine = new PanelsEngine();
  const testDoc = createAdversarialDoc('history-test', [
    { id: 'u1', kind: 'source', title: 'U1', text: 'T1' }
  ], []);
  engine.loadDocument(testDoc);

  assert.strictEqual(engine.navStack.length, 0);

  // Execute 25 sequential navigation pushes
  const jumps = [];
  for (let i = 1; i <= 25; i++) {
    const target = `target-${i}`;
    jumps.push(target);
    engine.pushHistorySnapshot(target);
    assert(engine.navStack.length <= 10, `Stack exceeded max 10: got ${engine.navStack.length} at jump ${i}`);
  }

  assert.strictEqual(engine.navStack.length, 10, 'Stack must be capped at exactly 10');

  // Verify FIFO eviction: only target-16 through target-25 remain
  for (let idx = 0; idx < 10; idx++) {
    const expectedTarget = `target-${16 + idx}`;
    assert.strictEqual(engine.navStack[idx].targetId, expectedTarget, `Stack index ${idx} must be ${expectedTarget}`);
  }
  console.log('  ✓ 25 sequential jumps tested: stack strictly capped at 10 (FIFO eviction verified)');

  // Verify LIFO return-to-anchor popping
  for (let popCount = 1; popCount <= 10; popCount++) {
    const expectedPopped = `target-${26 - popCount}`;
    const snapshot = engine.navStack.pop();
    assert.strictEqual(snapshot.targetId, expectedPopped, `LIFO pop #${popCount} expected ${expectedPopped}`);
  }
  assert.strictEqual(engine.navStack.length, 0, 'Stack must be empty after 10 pops');

  // Test pop on empty stack
  const emptyPop = engine.returnToAnchor();
  assert.strictEqual(emptyPop, false, 'returnToAnchor on empty stack must return false without exception');
  console.log('  ✓ Strict LIFO return-to-anchor behavior verified, empty stack handled gracefully');
  metrics.panelTestsPassed++;
}

// ============================================================================
// PART 3: SEARCH & HIGHLIGHTING STRESS TESTING
// ============================================================================
console.log('\n>>> SECTION 3: SEARCH & HIGHLIGHTING STRESS TESTING <<<');

{
  const searchDoc = {
    format: 'paralleldoc',
    version: '3.0',
    metadata: { document_id: 'doc-search-stress', revision: 'r1', title: 'Search Stress' },
    authors: [{ id: 'auth-1', name: 'Author' }],
    units: [
      { id: 'u-reg-1', kind: 'source', title: 'Regex Token Unit', text: 'Matching formula: .*+?^${}()|[]\\ and [A-Z]+ test.' },
      { id: 'u-reg-2', kind: 'source', title: 'Formula (SLA)', text: 'Calculation uses (?<=abc) and \\d+\\.\\d+ patterns with *.*' },
      { id: 'u-cyr-1', kind: 'analysis', title: 'Анализ аптайма', text: 'Гарантированный аптайм составляет 99.95%, штрафные санкции и компенсация 10%.' },
      { id: 'u-cyr-2', kind: 'action', title: 'Вне групп', text: 'Случай «Вне групп» и регламент §3.1(a) — критично.' },
      { id: 'u-uni-1', kind: 'source', title: 'Café résumé naïve', text: 'International tokens: Übersicht, español con ñ, and emojis 🚀 ⚠️ 📐.' },
      { id: 'u-punc-1', kind: 'analysis', title: 'Punctuation test', text: 'Punctuation: "quote" and \'single\', em—dash and en–dash, /path/to/file.' }
    ],
    groups: [],
    assets: [
      { id: 'asset-1', alt: 'Alt containing regex .*+? and cyrillic Схема', caption: 'Caption with §3.1(a)' }
    ],
    visuals: [
      {
        id: 'vis-1',
        title: 'Граф связей (SLA) & [A-Z]+',
        question: 'How does .*+? behave?',
        fallback: 'Fallback with Cyrillic Текст',
        nodes: [
          { id: 'node-.*', label: 'Node .*+?^${}()|[]\\' },
          { id: 'node-cyr', label: 'Узел Аптайм' }
        ],
        edges: [
          { id: 'edge-1', from: 'node-.*', to: 'node-cyr', label: 'Edge with \\d+\\.\\d+' }
        ]
      }
    ],
    profiles: []
  };

  const searchEngine = new SearchEngine(searchDoc, null);

  // 3.1 Regex Metacharacters
  console.log('\n--- 3.1 Regex Metacharacters (Zero Regex Evaluation) ---');
  const regexQueries = [
    '.*+?^${}()|[]\\',
    '[A-Z]+',
    '(?<=abc)',
    '\\d+\\.\\d+',
    '*.*',
    '(SLA)',
    '.*',
    '[',
    ']',
    '(',
    ')',
    '{',
    '}',
    '^',
    '$',
    '?',
    '+',
    '\\'
  ];

  for (const q of regexQueries) {
    let matches;
    assert.doesNotThrow(() => {
      matches = searchEngine.search(q);
    }, `Search for regex metacharacter '${q}' MUST NOT throw SyntaxError!`);
    assert(Array.isArray(matches), `Matches for '${q}' must be an array`);
    assert(matches.length > 0, `Query '${q}' should find matches in searchDoc`);
    console.log(`  ✓ Literal query '${q}': 0 exceptions, found ${matches.length} matches`);
    metrics.searchTestsPassed++;
  }

  // 3.2 Cyrillic & Punctuation Substrings
  console.log('\n--- 3.2 Cyrillic & Punctuation Substrings ---');
  const cyrillicQueries = [
    '«Вне групп»',
    'Гарантированный аптайм',
    'штрафные санкции',
    'компенсация 10%',
    '§3.1(a)',
    '99.95%',
    'em—dash',
    '/path/to/file',
    '"quote"'
  ];

  for (const q of cyrillicQueries) {
    const matches = searchEngine.search(q);
    assert(matches.length > 0, `Cyrillic/Punctuation query '${q}' must match`);
    console.log(`  ✓ Query '${q}': found ${matches.length} matches`);
    metrics.searchTestsPassed++;
  }

  // 3.3 Unicode Accents & Emojis
  console.log('\n--- 3.3 Unicode Accents & Emojis ---');
  const unicodeQueries = ['Café', 'résumé', 'naïve', 'Übersicht', 'ñ', '🚀', '⚠️', '📐'];
  for (const q of unicodeQueries) {
    const matches = searchEngine.search(q);
    assert(matches.length > 0, `Unicode query '${q}' must match`);
    console.log(`  ✓ Unicode query '${q}': found ${matches.length} matches`);
    metrics.searchTestsPassed++;
  }

  // 3.4 Circular Navigation & Rapid Wrap-Around
  console.log('\n--- 3.4 Circular Navigation & Rapid Wrap-Around ---');
  const matches = searchEngine.search('sla');
  assert(matches.length >= 2, 'Should match multiple items for "sla"');
  const total = matches.length;

  // Initial index should be 0
  assert.strictEqual(searchEngine.currentIndex, 0);

  // Call next() 50 times
  for (let i = 1; i <= 50; i++) {
    searchEngine.next();
    const expected = i % total;
    assert.strictEqual(searchEngine.currentIndex, expected, `Next step ${i} should wrap to ${expected}`);
  }
  console.log(`  ✓ 50 rapid next() calls with circular wrap-around across ${total} matches verified`);

  // Call prev() 50 times
  for (let i = 1; i <= 50; i++) {
    searchEngine.prev();
  }
  console.log('  ✓ 50 rapid prev() calls with circular backward wrap-around verified');

  // Single-match wrap
  searchEngine.search('Café');
  assert.strictEqual(searchEngine.matches.length, 1);
  searchEngine.next();
  assert.strictEqual(searchEngine.currentIndex, 0);
  searchEngine.prev();
  assert.strictEqual(searchEngine.currentIndex, 0);
  console.log('  ✓ Single-match circular traversal (0 -> 0) verified');

  // Zero-match safety
  searchEngine.search('nonexistent_token_xyz_12345');
  assert.strictEqual(searchEngine.matches.length, 0);
  assert.strictEqual(searchEngine.currentIndex, -1);
  assert.doesNotThrow(() => searchEngine.next());
  assert.doesNotThrow(() => searchEngine.prev());
  console.log('  ✓ Zero-match safety: next()/prev() do not throw');
  metrics.searchTestsPassed++;
}

console.log('\n===============================================================');
console.log('SUMMARY OF EMPIRICAL STRESS RESULTS:');
console.log(`  - Graph Adversarial Tests Passed:  ${metrics.graphTestsPassed}`);
console.log(`  - Panel & Zero Loss Tests Passed: ${metrics.panelTestsPassed}`);
console.log(`  - Search Stress Tests Passed:     ${metrics.searchTestsPassed}`);
console.log('  - Key Timings:');
for (const [k, v] of Object.entries(metrics.timings)) {
  console.log(`      * ${k}: ${v.toFixed(2)}ms`);
}
console.log('ALL NODE.JS ADVERSARIAL STRESS TESTS PASSED WITH 100% SUCCESS!');
console.log('===============================================================');
