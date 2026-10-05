import { createHash } from 'node:crypto';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { evaluateBatch } from './evaluate_batch.mjs';
import JevProvider from './providers/jev.mjs';

const args = process.argv.slice(2);
const option = key => {
  const i = args.indexOf(key);
  if (i < 0 || !args[i + 1] || args[i + 1].startsWith('--')) throw new Error(`Required: ${key}`);
  return args[i + 1];
};
const sha = bytes => 'sha256:' + createHash('sha256').update(bytes).digest('hex');
const studyBytes = await readFile(option('--study'));
const study = JSON.parse(studyBytes);
if (study.study_kind !== 'diagnostic_context_ablation' || study.holdout !== false || study.repeats !== 2) {
  throw new Error('Unsupported study');
}
if (JSON.stringify(study.arms) !== JSON.stringify(['code', 'code_task', 'code_task_facts']) ||
  !study.cases.length || new Set(study.cases.map(c => c.candidate_id)).size !== study.cases.length) {
  throw new Error('Invalid paired arms/cases');
}
const plan = [];
for (let repeat = 0; repeat < study.repeats; repeat++) {
  const cases = repeat === 0 ? study.cases : [...study.cases].reverse();
  for (const candidate of cases) {
    const arms = repeat === 0 ? study.arms : [...study.arms].reverse();
    for (const arm of arms) {
      const context = candidate.contexts[arm];
      if (sha(context.state) !== context.sha256 || Buffer.byteLength(context.state) > 24 * 1024 ||
        JSON.parse(context.state).candidate_id !== candidate.candidate_id) throw new Error('Invalid context');
      plan.push({ repeat, arm, candidate_id: candidate.candidate_id, context_sha256: context.sha256, state: context.state });
    }
  }
}
if (plan.length > 120) throw new Error('Request budget exceeds 120');
if (!args.includes('--allow-hosted')) {
  console.log(JSON.stringify({ requests: plan.length, study_sha256: sha(studyBytes),
    prompt_sha256: sha(JSON.stringify(study.prompt_config)), repeats: study.repeats, cache_replay: false }));
  process.exit(0);
}
if (!process.env.TYPESAFE_API_KEY) throw new Error('TYPESAFE_API_KEY is required');
const output = option('--output');
await mkdir(output);
const envelope = { study_sha256: sha(studyBytes), prompt_sha256: sha(JSON.stringify(study.prompt_config)),
  started_at: new Date().toISOString(), requested_model: study.prompt_config.model,
  model_revision: null, cache_replay: false, requests: plan.length, completed: false, rows: [] };
await writeFile(path.join(output, 'run.json'), JSON.stringify(envelope, null, 2) + '\n');
for (const item of plan) {
  const provider = new JevProvider({ id: 'baseline-v1', config: study.prompt_config });
  const summary = await evaluateBatch(item.state, [provider]);
  if (summary.results.length !== 1) throw new Error('Unexpected response count');
  const result = summary.results[0];
  envelope.rows.push({ repeat: item.repeat, arm: item.arm, candidate_id: item.candidate_id,
    context_sha256: item.context_sha256, response: result.response,
    error: result.error, received_at: new Date().toISOString() });
  envelope.completed = envelope.rows.length === plan.length;
  await writeFile(path.join(output, 'run.json'), JSON.stringify(envelope, null, 2) + '\n');
  console.log(`Context experiment: ${envelope.rows.length}/${plan.length} responses saved`);
}
