'use strict';
// Run the actual UI state functions without a DOM: aggregation must not fabricate member visits.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const saved = {};
const group = { note_ids: ['a', 'b', 'c'], content_digest: 'current' };
const state = { data: { name: 'demo' }, notesData: { collections: [{ reading_members: { a: group } }] } };
const read = new Set();
const context = vm.createContext({ state, read,
  stored: (key, fallback) => JSON.parse(JSON.stringify(saved[key] ?? fallback)),
  store: (key, value) => { saved[key] = JSON.parse(JSON.stringify(value)); } });
vm.runInContext(fs.readFileSync(path.join(__dirname, '../skills/interview-bank/assets/web/notes-ui.js'), 'utf8'), context);
const key = 'ibank-notes-learning:demo';
let checks = 0;
function equal(expression, expected) { assert.equal(vm.runInContext(expression, context), expected); checks++; }
equal("noteLearningState('a')", 'unread');
saved[key] = { a: { state: 'read' } };
equal("noteLearningState('a')", 'unread');  // The first fragment alone is not the whole article.
saved[key].b = { state: 'mastered' };
saved[key].c = { state: 'read' };
equal("noteLearningState('a')", 'read');
saved[key].b.state = 'review';
equal("noteLearningState('a')", 'review');
vm.runInContext("recordNoteVisit('a')", context);
equal("noteLearningState('a')", 'review');
assert.deepEqual(saved[key].b, { state: 'review' }); checks++;
assert.deepEqual(saved[key].c, { state: 'read' }); checks++;
saved[key].a = { state: 'mastered', reading_digest: 'current' };
equal("noteLearningState('a')", 'mastered');
saved[key].a = { state: 'unread', reading_digest: 'current' };
equal("noteLearningState('a')", 'unread');
saved[key].a.reading_digest = 'old';
equal("noteLearningState('a')", 'review');  // An obsolete group action cannot suppress a member's review flag.
saved[key] = {}; read.clear();
vm.runInContext("recordNoteVisit('a')", context);
equal("noteLearningState('a')", 'read');
assert.deepEqual(Object.keys(saved[key]), ['a']); checks++;
state.notesData = null;
equal("noteLearningState('a')", 'read');
saved[key].a.state = 'unread';
read.add('a');
equal("noteLearningState('a')", 'unread');
console.log(JSON.stringify({ reading_progress_checks: checks, status: 'passed' }));
