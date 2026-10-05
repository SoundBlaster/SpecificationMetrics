import { createHash } from 'node:crypto';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'yaml';
import { evaluateBatch } from './evaluate_batch.mjs';
import JevProvider from './providers/jev.mjs';

const root = path.dirname(fileURLToPath(import.meta.url));
const sha = bytes => 'sha256:' + createHash('sha256').update(bytes).digest('hex');
const args = process.argv.slice(2);
const option = key => {
  const i = args.indexOf(key);
  if (i < 0 || !args[i + 1] || args[i + 1].startsWith('--')) throw new Error(`Required: ${key}`);
  return args[i + 1];
};
const phase = option('--phase');
if (!['development', 'holdout'].includes(phase)) throw new Error('Unknown phase');
const manifestBytes = await readFile(option('--manifest'));
const manifest = JSON.parse(manifestBytes);
const manifestHash = sha(manifestBytes);
const original = parse(await readFile(path.join(root, 'promptfooconfig.yaml'), 'utf8'));
const baseline = original.providers[0].config;
const additions = {
  'singleton-v1': ' A stable domain rule appearing once may still be eligible. Repetition is evidence of reuse, not a requirement.',
  'owned-rule-v1': ' Classify the exact selected site. Exclude a rule already expressed by a named Specification or its composition; a nearby Specification call does not exclude other inline rules.',
  'mechanical-boundary-v1': ' Hashing, serialization and input shape validation alone are mechanics. A check that uses their result to admit a product or authorize an action may instead express policy. Judge the rule being decided, not the technical operation used.',
  'bounded-evidence-v1': ' Do not infer eligibility from length, require() calls or policy-sounding names. If the exact site mixes unrelated decisions or omitted context prevents locating a stable rule, choose needs_review.',
};
const configs = { 'baseline-v1': structuredClone(baseline), 'boundary-test-v2': original.providers[1].config };
for (const [id, extra] of Object.entries(additions)) {
  configs[id] = structuredClone(baseline);
  configs[id].questions.opportunity.instructions += extra;
}
let variantIds = Object.keys(configs);
let finalistsHash = null;
if (phase === 'holdout') {
  const finalistBytes = await readFile(option('--finalists'));
  const finalists = JSON.parse(finalistBytes);
  if (finalists.manifest_sha256 !== manifestHash) throw new Error('Finalist manifest mismatch');
  finalistsHash = sha(finalistBytes);
  variantIds = finalists.variant_ids;
  if (variantIds.length !== 2 || variantIds[0] !== 'baseline-v1' || new Set(variantIds).size !== 2) {
    throw new Error('Holdout must compare baseline and one frozen challenger');
  }
  for (const id of variantIds) {
    if (!configs[id] || JSON.stringify(configs[id]) !== JSON.stringify(finalists.prompt_configs[id])) {
      throw new Error('Prompt changed after development selection');
    }
  }
}
const cases = manifest.cases.filter(c => phase === 'development'
  ? manifest.screening_ids.includes(c.candidate_id) : c.split === 'holdout');
if (!cases.length || cases.some(c => c.split !== phase || sha(c.context) !== c.context_sha256)) {
  throw new Error('Invalid input split or context digest');
}
const requests = cases.length * variantIds.length;
if (requests > 120) throw new Error('Per-run hosted request budget exceeds 120');
const effectiveConfigs = Object.fromEntries(variantIds.map(v => [v, configs[v]]));
const plan = { phase, candidate_ids: cases.map(c => c.candidate_id), variant_ids: variantIds,
  requests, manifest_sha256: manifestHash, finalists_sha256: finalistsHash,
  prompt_configs: effectiveConfigs, prompt_configs_sha256: sha(JSON.stringify(effectiveConfigs)),
  model_revision: null, cache_replay: false, reference_kind: manifest.reference_kind };
if (!args.includes('--allow-hosted')) {
  console.log(JSON.stringify({ ...plan, prompt_configs: undefined }, null, 2));
  process.exit(0);
}
if (!process.env.TYPESAFE_API_KEY) throw new Error('TYPESAFE_API_KEY is required');
if (phase === 'holdout') {
  await writeFile(option('--finalists') + '.holdout-started', JSON.stringify({ manifestHash, finalistsHash }), { flag: 'wx' });
}
const outputDir = option('--output');
// An exclusive run directory prevents a failed/repeated run from replacing receipts.
await mkdir(outputDir);
await writeFile(path.join(outputDir, 'plan.json'), JSON.stringify(plan, null, 2) + '\n');
const results = [];
let tokenUsage = 0;
const startedAt = (new Date()).toISOString();
for (const candidate of cases) {
  const providers = variantIds.map(id => new JevProvider({ id, config: configs[id] }));
  // One candidate per evaluation saves progress after each bounded group.
  const evaluated = await evaluateBatch(candidate.context, providers);
  results.push(...evaluated.results);
  tokenUsage += evaluated.stats?.tokenUsage?.total ?? 0;
  const envelope = { ...plan, started_at: startedAt, updated_at: (new Date()).toISOString(),
    completed: results.length === requests,
    results: { results }, token_usage_total: tokenUsage };
  await writeFile(path.join(outputDir, 'run.json'), JSON.stringify(envelope, null, 2) + '\n');
  console.log(`${phase}: ${results.length}/${requests} responses saved`);
}
