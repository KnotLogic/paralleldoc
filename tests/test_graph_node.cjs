/**
 * tests/test_graph_node.cjs — Node.js Unit Verification for src/graph.js
 * Verifies cycle tolerance, scale guard, 6 relation types, and deterministic layout.
 */

const assert = require('assert');
const {
  RELATION_CONFIG,
  SCALE_GUARD_MAX_NODES,
  SCALE_GUARD_MAX_EDGES,
  checkScaleGuard,
  computeGraphLayout
} = require('../src/graph.js');

console.log('--- RUNNING GRAPH UNIT TESTS (Node.js) ---');

// 1. Verify 6 Typed Relations and Semantics
console.log('1. Testing 6 typed relations...');
const expectedRelations = ['supports', 'qualifies', 'contradicts', 'depends_on', 'precedes', 'compares'];
for (const rel of expectedRelations) {
  assert(RELATION_CONFIG[rel], `Relation ${rel} must exist in RELATION_CONFIG`);
  assert(RELATION_CONFIG[rel].nameRu, `Relation ${rel} must have Russian name`);
  assert(RELATION_CONFIG[rel].color, `Relation ${rel} must have distinct color`);
}

// Check directionality & markers
assert.strictEqual(RELATION_CONFIG.supports.directed, true);
assert.strictEqual(RELATION_CONFIG.supports.markerId, 'arrow-supports');
assert.strictEqual(RELATION_CONFIG.qualifies.directed, true);
assert.strictEqual(RELATION_CONFIG.contradicts.directed, true);
assert.strictEqual(RELATION_CONFIG.depends_on.directed, true);
assert.strictEqual(RELATION_CONFIG.precedes.directed, true);
assert.strictEqual(RELATION_CONFIG.compares.directed, false, 'compares must be symmetric (undirected)');
assert.strictEqual(RELATION_CONFIG.compares.markerId, null, 'compares must not have arrow marker');
console.log('   ✓ 6 typed relations verified with correct directionality & markers');

// 2. Test Cycle Tolerance in depends_on and other edges
console.log('2. Testing cycle tolerance...');

// 2a. Mutual cycle: N1 -> N2 and N2 -> N1
const mutualCycleNodes = [
  { id: 'node-A', label: 'Premise A', unit_refs: ['u-A'] },
  { id: 'node-B', label: 'Premise B', unit_refs: ['u-B'] }
];
const mutualCycleEdges = [
  { id: 'e1', from: 'node-A', to: 'node-B', relation: 'depends_on', label: 'A depends on B', unit_refs: ['u-A'] },
  { id: 'e2', from: 'node-B', to: 'node-A', relation: 'depends_on', label: 'B depends on A', unit_refs: ['u-B'] }
];

const startMutual = performance.now();
const mutualLayout = computeGraphLayout(mutualCycleNodes, mutualCycleEdges, 800, 500);
const elapsedMutual = performance.now() - startMutual;

assert.strictEqual(mutualLayout.nodes.length, 2);
assert(isFinite(mutualLayout.nodes[0].x) && isFinite(mutualLayout.nodes[0].y), 'Coordinates must be finite numbers');
assert(isFinite(mutualLayout.nodes[1].x) && isFinite(mutualLayout.nodes[1].y), 'Coordinates must be finite numbers');
assert(elapsedMutual < 50, `Mutual cycle layout took ${elapsedMutual.toFixed(2)}ms (expected < 50ms)`);
console.log(`   ✓ Mutual 2-node cycle resolved in ${elapsedMutual.toFixed(2)}ms`);

// 2b. Complex 100-node circular chain with cross-links
const chainNodes = [];
const chainEdges = [];
for (let i = 0; i < 100; i++) {
  chainNodes.push({ id: `n-${i}`, label: `Assertion ${i}`, unit_refs: [`u-${i}`] });
  chainEdges.push({
    id: `e-${i}`,
    from: `n-${i}`,
    to: `n-${(i + 1) % 100}`,
    relation: 'depends_on',
    label: `Depends ${i}->${(i + 1) % 100}`,
    unit_refs: []
  });
  if (i % 5 === 0 && i > 10) {
    chainEdges.push({
      id: `e-cross-${i}`,
      from: `n-${i}`,
      to: `n-${i - 10}`,
      relation: 'contradicts',
      label: 'Cross link',
      unit_refs: []
    });
  }
}

const startStress = performance.now();
const stressLayout = computeGraphLayout(chainNodes, chainEdges, 1000, 700);
const elapsedStress = performance.now() - startStress;

assert.strictEqual(stressLayout.nodes.length, 100);
for (const n of stressLayout.nodes) {
  assert(isFinite(n.x) && isFinite(n.y), `Node ${n.id} must have valid coordinates`);
}
assert(elapsedStress < 150, `100-node stress graph took ${elapsedStress.toFixed(2)}ms (expected < 150ms)`);
console.log(`   ✓ 100-node circular graph with cross-links resolved in ${elapsedStress.toFixed(2)}ms`);

// 3. Test Determinism (Identical coordinates on rerun)
console.log('3. Testing layout determinism...');
const run1 = computeGraphLayout(chainNodes.slice(0, 10), chainEdges.slice(0, 10), 800, 500);
const run2 = computeGraphLayout(chainNodes.slice(0, 10), chainEdges.slice(0, 10), 800, 500);
for (let i = 0; i < run1.nodes.length; i++) {
  assert.strictEqual(run1.nodes[i].x.toFixed(4), run2.nodes[i].x.toFixed(4), `Node ${i} X coordinate must be deterministic`);
  assert.strictEqual(run1.nodes[i].y.toFixed(4), run2.nodes[i].y.toFixed(4), `Node ${i} Y coordinate must be deterministic`);
}
console.log('   ✓ Layout is 100% mathematically deterministic across identical runs');

// 4. Test Scale Limit Guard (AC-44: > 200 nodes or > 400 edges)
console.log('4. Testing scale limit guard (AC-44)...');

// 4a. Under limit (200 nodes, 400 edges) -> not breached
const normalNodes = Array.from({ length: 200 }, (_, i) => ({ id: `node-${i}` }));
const normalEdges = Array.from({ length: 400 }, (_, i) => ({ id: `edge-${i}` }));
const normalCheck = checkScaleGuard({ nodes: normalNodes, edges: normalEdges });
assert.strictEqual(normalCheck.breached, false, 'Scale guard should not breach at exactly 200 nodes and 400 edges');

// 4b. Over node limit (201 nodes) -> breached
const overNodes = Array.from({ length: 201 }, (_, i) => ({ id: `node-${i}` }));
const overNodesCheck = checkScaleGuard({ nodes: overNodes, edges: [] });
assert.strictEqual(overNodesCheck.breached, true, 'Scale guard must breach at 201 nodes');
assert(overNodesCheck.message.includes('AC-44'), 'Warning message must cite AC-44');

// 4c. Over edge limit (401 edges) -> breached
const overEdges = Array.from({ length: 401 }, (_, i) => ({ id: `edge-${i}` }));
const overEdgesCheck = checkScaleGuard({ nodes: [], edges: overEdges });
assert.strictEqual(overEdgesCheck.breached, true, 'Scale guard must breach at 401 edges');
assert(overEdgesCheck.message.includes('AC-44'), 'Warning message must cite AC-44');
console.log('   ✓ Scale limit guard correctly identifies boundaries (200n / 400e)');

console.log('=== ALL GRAPH NODE.JS TESTS PASSED SUCCESSFULLY ===');
