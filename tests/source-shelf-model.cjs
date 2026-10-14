'use strict';
// No browser or npm packages: exercise persisted preferences and reorder invariants.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const context = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../skills/interview-bank/assets/web/source-shelf.js'), 'utf8'), context);
const model = vm.runInContext('sourceShelf.model', context);
const plain = value => JSON.parse(JSON.stringify(value));
const names = ['agent', 'java', 'rag'];
const defaults = { version: 1, order: names, expanded: [] };
let checks = 0;
const equal = (a, b) => { assert.deepEqual(plain(a), b); checks++; };
for (const value of [null, 42, 'bad', {}, { version: 2, order: ['rag'], expanded: ['rag'] }]) equal(model.normalize(value, names), defaults);
equal(model.normalize({ version: 1, order: ['rag', 'gone', 'rag', {}, 'agent'], expanded: ['java', 'gone', 'java'] }, names),
  { version: 1, order: ['rag', 'agent', 'java'], expanded: ['java'] });
equal(model.normalize({ version: 1, order: names, expanded: ['agent'] }, ['java', 'rag', 'new-source']),
  { version: 1, order: ['java', 'rag', 'new-source'], expanded: [] });
equal(model.normalize({ version: 1, order: 'bad', expanded: {} }, names), defaults);
equal(model.move(names, 'agent', 2), ['java', 'rag', 'agent']);
equal(model.move(names, 'rag', 0), ['rag', 'agent', 'java']);
equal(model.move(names, 'java', 999), ['agent', 'rag', 'java']);
equal(model.move(names, 'java', -9), ['java', 'agent', 'rag']);
equal(model.move(names, 'missing', 1), names);
equal(model.move(names, 'java', '1'), names);
equal(model.move(names, 'java', NaN), names);
equal(names, ['agent', 'java', 'rag']);
for (const id of names) for (const position of [0, 1, 2]) {
  const moved = model.move(names, id, position);
  equal([...moved].sort(), [...names].sort());
  equal(moved[position], id);
  const prefs = model.normalize({ version: 1, order: moved, expanded: ['java'] }, names);
  equal(model.normalize(prefs, names), plain(prefs));
}
console.log(JSON.stringify({ source_shelf_model_checks: checks, status: 'passed' }));
