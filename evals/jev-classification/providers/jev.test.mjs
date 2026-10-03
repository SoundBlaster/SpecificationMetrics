import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import JevProvider from './jev.mjs';

const previousKey = process.env.TYPESAFE_API_KEY;
const previousFetch = globalThis.fetch;

afterEach(() => {
  if (previousKey === undefined) delete process.env.TYPESAFE_API_KEY;
  else process.env.TYPESAFE_API_KEY = previousKey;
  globalThis.fetch = previousFetch;
});

test('requires a key without making a request', async () => {
  delete process.env.TYPESAFE_API_KEY;
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    throw new Error('fetch should not run');
  };

  const result = await new JevProvider({}).callApi('{"candidate":"fixture"}');
  assert.match(result.error, /TYPESAFE_API_KEY is required/);
  assert.equal(calls, 0);
});

test('sends one typed request and preserves Jev output metadata', async () => {
  process.env.TYPESAFE_API_KEY = 'fixture-key';
  const question = { type: 'choice', instructions: 'Choose one', criteria: { yes: 'Yes' } };
  const responseBody = {
    model: 'jev-1.13.0',
    answers: { opportunity: { type: 'choice', choice: 'eligible', confidence: 0.7, probabilities: { eligible: 0.7 } } },
    usage: { input_tokens: 10, output_tokens: 2 },
  };
  let calls = 0;
  globalThis.fetch = async (url, options) => {
    calls += 1;
    assert.equal(url, 'https://api.typesafe.ai/v1/systemone');
    assert.equal(options.method, 'POST');
    assert.equal(options.redirect, 'error');
    assert.equal(options.headers.authorization, 'Bearer fixture-key');
    const body = JSON.parse(options.body);
    assert.equal(body.model, 'jev-1.13.0');
    assert.deepEqual(body.state, { candidate: 'fixture' });
    assert.deepEqual(body.questions, { opportunity: question });
    return new Response(JSON.stringify(responseBody), { status: 200 });
  };

  const result = await new JevProvider({ config: { questions: { opportunity: question } } })
    .callApi('{"candidate":"fixture"}');
  assert.equal(calls, 1);
  assert.deepEqual(result.output, responseBody.answers);
  assert.deepEqual(result.tokenUsage, { prompt: 10, completion: 2, total: 12 });
  assert.equal(result.metadata.typesafe.returnedModel, 'jev-1.13.0');
  assert.deepEqual(result.metadata.typesafe.usage, responseBody.usage);
});

test('does not retry an HTTP error or include response details', async () => {
  process.env.TYPESAFE_API_KEY = 'fixture-key';
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return new Response('private provider body', { status: 503 });
  };

  const result = await new JevProvider({}).callApi('{"candidate":"fixture"}');
  assert.equal(calls, 1);
  assert.equal(result.error, 'TypeSafe Jev returned HTTP 503');
  assert.doesNotMatch(result.error, /fixture-key|private provider body/);
});
