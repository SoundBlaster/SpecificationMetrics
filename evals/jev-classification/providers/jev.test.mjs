import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { cache, evaluate } from 'promptfoo';
import { readFileSync } from 'node:fs';
import { parse } from 'yaml';
import JevProvider from './jev.mjs';

cache.disableCache();

const previousKey = process.env.TYPESAFE_API_KEY;
const previousFetch = globalThis.fetch;

afterEach(() => {
  if (previousKey === undefined) delete process.env.TYPESAFE_API_KEY;
  else process.env.TYPESAFE_API_KEY = previousKey;
  globalThis.fetch = previousFetch;
  cache.disableCache();
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


test('pinned Promptfoo renders checked-in JSON without hosted requests', async () => {
  const config = parse(readFileSync(new URL('../promptfooconfig.yaml', import.meta.url), 'utf8'));
  const cases = JSON.parse(readFileSync(new URL('../cases.json', import.meta.url), 'utf8'));
  let calls = 0;
  const provider = { id: () => 'offline-render-fixture', callApi: async (prompt) => {
    assert.deepEqual(JSON.parse(prompt), JSON.parse(cases[0].vars.candidate_json));
    calls += 1;
    return { output: 'fixture' };
  } };
  await evaluate({ prompts: config.prompts, providers: [provider], tests: [{ vars: cases[0].vars }] },
    { cache: false, writeResults: false, maxConcurrency: 1 });
  assert.equal(calls, config.prompts.length);
});

test('Promptfoo cache replays success, partitions prompts and respects no-cache', async () => {
  process.env.TYPESAFE_API_KEY = 'fixture-cache-key';
  const namespace = 'offline-jev-' + crypto.randomUUID();
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return new Response(JSON.stringify({ model: 'fixture-model', answers: { choice: 'fixture' } }));
  };
  await cache.withCacheNamespace(namespace, async () => {
    cache.enableCache();
    const provider = new JevProvider({});
    const first = await provider.callApi('{"candidate":"fixture"}');
    const second = await provider.callApi('{"candidate":"fixture"}');
    assert.equal(first.cached, false);
    assert.equal(second.cached, true);
    assert.deepEqual(second.output, first.output);
    assert.equal(calls, 1);
    await provider.callApi('{"candidate":"changed"}');
    assert.equal(calls, 2);
    process.env.TYPESAFE_API_KEY = 'different-fixture-key';
    await provider.callApi('{"candidate":"fixture"}');
    assert.equal(calls, 3);
    await new JevProvider({ config: { questions: { changed: {} } } }).callApi('{"candidate":"fixture"}');
    assert.equal(calls, 4);
    await new JevProvider({ config: { model: 'different-model' } }).callApi('{"candidate":"fixture"}');
    assert.equal(calls, 5);
    cache.disableCache();
    await provider.callApi('{"candidate":"fixture"}');
    assert.equal(calls, 6);
  });
});

test('malformed and oversized responses are not cached', async () => {
  process.env.TYPESAFE_API_KEY = 'fixture-cache-key';
  for (const [body, status] of [['{', 200], ['x'.repeat(1024 * 1024 + 1), 200], ['unavailable', 503]]) {
    let calls = 0;
    globalThis.fetch = async () => { calls += 1; return new Response(body, { status }); };
    await cache.withCacheNamespace('invalid-' + crypto.randomUUID(), async () => {
      cache.enableCache();
      const provider = new JevProvider({});
      assert.ok((await provider.callApi('{}')).error);
      assert.ok((await provider.callApi('{}')).error);
      assert.equal(calls, 2);
    });
  }
});
