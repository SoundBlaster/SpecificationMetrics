import test from 'node:test';
import assert from 'node:assert/strict';
import { evaluateBatch } from './evaluate_batch.mjs';

test('pinned Promptfoo summary preserves provider IDs, state and failures', async () => {
  const state = JSON.stringify({ candidate_id: 'opaque-test', site: { code: 'if allowed: pass' } });
  const summary = await evaluateBatch(state, [
    { id: () => 'baseline-v1', callApi: async prompt => {
      assert.deepEqual(JSON.parse(prompt), JSON.parse(state));
      return { output: { opportunity: { choice: 'eligible' }, concern_kind: { choice: 'policy' } } };
    } },
    { id: () => 'fixture-error', callApi: async () => ({ error: 'fixture-provider-error' }) },
  ]);
  assert.equal(summary.results.length, 2);
  assert.equal(summary.results[0].provider.id, 'baseline-v1');
  assert.equal(summary.results[0].vars.candidate_json, state);
  assert.equal(summary.results[0].response.output.opportunity.choice, 'eligible');
  assert.equal(summary.results[1].provider.id, 'fixture-error');
  assert.match(summary.results[1].response.error, /fixture-provider-error/);
});
