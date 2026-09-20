/**
 * tests/test_panels_node.cjs — Node.js Unit Verification for src/panels.js
 * Verifies zero unit loss, missing role badges, orphan reconciliation,
 * profile switching, and 10-target history stack.
 */

const assert = require('assert');
const {
  BUILTIN_PROFILES,
  MISSING_ROLE_CONFIG,
  PanelsEngine
} = require('../src/panels.js');

console.log('--- RUNNING PANELS UNIT TESTS (Node.js) ---');

// 1. Builtin Profiles Structure
console.log('1. Verifying Builtin Profiles...');
assert(BUILTIN_PROFILES['builtin:2'], 'builtin:2 must exist');
assert(BUILTIN_PROFILES['builtin:3'], 'builtin:3 must exist');
assert(BUILTIN_PROFILES['builtin:4'], 'builtin:4 must exist');

// Check Compare (builtin:2) has 2 panels (50/50) + model strip
assert.strictEqual(BUILTIN_PROFILES['builtin:2'].panels.length, 2);
assert.strictEqual(BUILTIN_PROFILES['builtin:2'].panels[0].weight, 50);
assert.strictEqual(BUILTIN_PROFILES['builtin:2'].panels[1].weight, 50);
assert.strictEqual(BUILTIN_PROFILES['builtin:2'].hasModelStrip, true, 'builtin:2 must have model strip');

// Check Evidence (builtin:3) has 3 panels (32/36/32)
assert.strictEqual(BUILTIN_PROFILES['builtin:3'].panels.length, 3);
assert.strictEqual(BUILTIN_PROFILES['builtin:3'].panels[0].weight, 32);
assert.strictEqual(BUILTIN_PROFILES['builtin:3'].panels[1].weight, 36);
assert.strictEqual(BUILTIN_PROFILES['builtin:3'].panels[2].weight, 32);

// Check Review (builtin:4) has 4 panels (28/30/26/16)
assert.strictEqual(BUILTIN_PROFILES['builtin:4'].panels.length, 4);
assert.strictEqual(BUILTIN_PROFILES['builtin:4'].panels[0].weight, 28);
assert.strictEqual(BUILTIN_PROFILES['builtin:4'].panels[1].weight, 30);
assert.strictEqual(BUILTIN_PROFILES['builtin:4'].panels[2].weight, 26);
assert.strictEqual(BUILTIN_PROFILES['builtin:4'].panels[3].weight, 16);
console.log('   ✓ Builtin profiles structure and weights verified');

// 2. Document Loading & Orphan Unit Reconciliation
console.log('2. Testing Document Ingestion & Orphan Reconciliation...');
const engine = new PanelsEngine();

const testDoc = {
  format: 'paralleldoc',
  version: '3.0',
  metadata: {
    document_id: 'doc-sla-test',
    revision: 'r1',
    title: 'Cloud Service SLA Review',
    author_refs: ['auth-1']
  },
  authors: [
    { id: 'auth-1', kind: 'human', name: 'Lead Auditor' }
  ],
  units: [
    { id: 'u-src-1', kind: 'source', title: 'SLA Clause 4.1', text: 'Uptime 99.95%', author_refs: ['auth-1'], epistemic: 'reported', status: 'done' },
    { id: 'u-mod-1', kind: 'model', title: 'Formal Uptime Model', text: 'Mathematical SLA model', author_refs: ['auth-1'], epistemic: 'hypothesis', status: 'reviewed' },
    { id: 'u-ana-1', kind: 'analysis', title: 'Downtime Analysis', text: 'Max allowable downtime', author_refs: ['auth-1'], epistemic: 'supported', status: 'reviewed', source_refs: ['u-src-1'] },
    { id: 'u-act-1', kind: 'action', title: 'Remediation Step', text: 'Deploy monitoring probes', author_refs: ['auth-1'], epistemic: 'not-applicable', status: 'draft' },
    // Group 2 with missing analysis & action
    { id: 'u-src-2', kind: 'source', title: 'SLA Clause 4.2', text: 'Maintenance window exclusion', author_refs: ['auth-1'], epistemic: 'reported', status: 'done' },
    // Orphan unit not in any group
    { id: 'u-orphan-1', kind: 'analysis', title: 'Orphan Finding', text: 'Standalone calculation', author_refs: ['auth-1'], epistemic: 'unknown', status: 'draft' }
  ],
  groups: [
    { id: 'g-1', title: 'Group 1: Primary Uptime', unit_refs: ['u-src-1', 'u-mod-1', 'u-ana-1', 'u-act-1'] },
    { id: 'g-2', title: 'Group 2: Maintenance Exclusion', unit_refs: ['u-src-2'] }
  ],
  visuals: [],
  assets: [],
  profiles: []
};

engine.loadDocument(testDoc);

assert.strictEqual(engine.unitMap.size, 6, 'All 6 units must be indexed');
assert.strictEqual(engine.orphanUnits.length, 1, '1 orphan unit must be detected');
assert.strictEqual(engine.orphanUnits[0].id, 'u-orphan-1');
assert.strictEqual(engine.groupList.length, 3, 'Group list must have 2 doc groups + 1 synthesized orphan group');
assert.strictEqual(engine.groupList[2].id, '__orphans__');
assert.strictEqual(engine.groupList[2].isOrphanGroup, true);
console.log('   ✓ Orphan units reconciled under «Вне групп»');

// 3. ZERO UNIT LOSS Invariant across ALL Profiles (AC-11)
console.log('3. Testing ZERO UNIT LOSS invariant across all profiles...');
const expectedTotalUnits = testDoc.units.length; // 6 units

for (const profileId of ['builtin:2', 'builtin:3', 'builtin:4']) {
  engine.setProfile(profileId);
  const plan = engine.getRenderPlan();

  assert.strictEqual(
    plan.totalUnitsCount,
    expectedTotalUnits,
    `Profile ${profileId} must render EXACTLY ${expectedTotalUnits} units, but got ${plan.totalUnitsCount}`
  );
  console.log(`   ✓ Profile ${profileId}: rendered ${plan.totalUnitsCount}/${expectedTotalUnits} units (ZERO LOSS)`);
}

// 4. Explicit Missing Role Badges (F21)
console.log('4. Testing Explicit Missing Role Badges...');
engine.setProfile('builtin:4'); // Review: Source / Model / Analysis / Action
const planReview = engine.getRenderPlan();

// In Group 2 (g-2), only 'source' is present, so 'model', 'analysis', 'action' should be missing
const g2Plan = planReview.groups.find(g => g.groupId === 'g-2');
assert(g2Plan, 'Group g-2 plan must exist');

const missingInG2 = [];
g2Plan.panels.forEach(p => missingInG2.push(...p.missingRoles));
assert(missingInG2.includes('model'), 'Missing model badge must be recorded for g-2');
assert(missingInG2.includes('analysis'), 'Missing analysis badge must be recorded for g-2');
assert(missingInG2.includes('action'), 'Missing action badge must be recorded for g-2');

assert.strictEqual(MISSING_ROLE_CONFIG.analysis.text, '«Нет анализа»');
assert.strictEqual(MISSING_ROLE_CONFIG.action.text, '«Действие не задано»');
console.log('   ✓ Missing roles explicitly identified with spec-compliant badges');

// 5. 10-Target History Stack LIFO Behavior (AC-16)
console.log('5. Testing 10-Target History Stack LIFO Behavior...');
assert.strictEqual(engine.navStack.length, 0);

// Push 12 targets
for (let i = 1; i <= 12; i++) {
  engine.pushHistorySnapshot(`target-${i}`);
}

assert.strictEqual(engine.navStack.length, 10, 'History stack capacity must be capped at 10');
assert.strictEqual(engine.navStack[engine.navStack.length - 1].targetId, 'target-12', 'Top of stack should be target-12');
assert.strictEqual(engine.navStack[0].targetId, 'target-3', 'Oldest items (target-1, target-2) must be evicted');

// Test return-to-anchor LIFO pop
const pop1 = engine.navStack.pop();
assert.strictEqual(pop1.targetId, 'target-12');
const pop2 = engine.navStack.pop();
assert.strictEqual(pop2.targetId, 'target-11');
assert.strictEqual(engine.navStack.length, 8);
console.log('   ✓ 10-target history stack maintains strict LIFO and eviction bounds');

// 6. Non-v3 Format Rejection
console.log('6. Testing strict non-v3 rejection...');
assert.throws(() => {
  engine.loadDocument({ format: 'legacy_v2', version: '2.1' });
}, /Неподдерживаемый формат; требуется ParallelDoc 3.0/);

console.log('=== ALL PANELS NODE.JS TESTS PASSED SUCCESSFULLY ===');
