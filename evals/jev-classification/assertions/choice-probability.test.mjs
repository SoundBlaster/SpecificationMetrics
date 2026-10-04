import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import test from 'node:test';

const evaluate = createRequire(import.meta.url)('./choice-probability.js');
const context = {
  config: { axis: 'opportunity' },
  vars: { expected_opportunity: 'eligible', label_status: 'pilot_hypothesis' },
};

test('categorical score measures label agreement, not uncalibrated probability', () => {
  const correct = evaluate({ opportunity: { choice: 'eligible', probabilities: { eligible: 0.44 } } }, context);
  assert.equal(correct.pass, true);
  assert.equal(correct.score, 1);
  assert.match(correct.reason, /expected_label_probability=0.44/);
  const incorrect = evaluate({ opportunity: { choice: 'excluded', probabilities: { eligible: 0.49 } } }, context);
  assert.equal(incorrect.pass, false);
  assert.equal(incorrect.score, 0);
});

test('provider failure cannot become a successful categorical classification', () => {
  assert.equal(evaluate({}, context).pass, false);
  assert.equal(evaluate({}, context).score, 0);
});
