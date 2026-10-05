import { createHash } from 'node:crypto';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { evaluateBatch } from './evaluate_batch.mjs';
import JevProvider from './providers/jev.mjs';

const args = process.argv.slice(2);
const option = key => {
  const index = args.indexOf(key);
  if (index < 0 || !args[index + 1] || args[index + 1].startsWith('--')) throw new Error(`Required: ${key}`);
  return args[index + 1];
};
const sha = bytes => 'sha256:' + createHash('sha256').update(bytes).digest('hex');
const studyBytes = await readFile(option('--study'));
const study = JSON.parse(studyBytes);
if (study.study_kind !== 'diagnostic_specificationcore_goal_profile_ablation' || study.holdout !== false || study.repeats !== 2 ||
  JSON.stringify(study.arms) !== JSON.stringify(['code', 'code_plus_architecture_profile']) ||
  !study.cases.length || new Set(study.cases.map(candidate => candidate.candidate_id)).size !== study.cases.length) {
  throw new Error('Unsupported or invalid study');
}
const profileBytes = await readFile(new URL(study.architecture_profile.path, import.meta.url));
if (sha(profileBytes) !== study.architecture_profile.sha256) throw new Error('Architecture profile digest mismatch');
const plan = [];
for (let repeat = 0; repeat < study.repeats; repeat++) {
  const candidates = repeat === 0 ? study.cases : [...study.cases].reverse();
  for (const candidate of candidates) {
    const arms = repeat === 0 ? study.arms : [...study.arms].reverse();
    for (const arm of arms) {
      const context = candidate.contexts[arm];
      const state = JSON.parse(context.state);
      if (sha(context.state) !== context.sha256 || Buffer.byteLength(context.state) > 24 * 1024 || state.candidate_id !== candidate.candidate_id ||
        (arm === 'code') === Object.hasOwn(state, 'architecture_profile')) throw new Error('Invalid paired context');
      plan.push({ repeat, arm, candidate_id: candidate.candidate_id, context_sha256: context.sha256, state: context.state });
    }
  }
}
if (plan.length !== study.cases.length * study.arms.length * study.repeats || plan.length > 40) throw new Error('Invalid request budget');
const base = { requests: plan.length, study_sha256: sha(studyBytes),
  prompt_sha256: sha(JSON.stringify(study.prompt_config)), architecture_profile_sha256: study.architecture_profile.sha256,
  repeats: study.repeats, cache_replay: false };
if (!args.includes('--allow-hosted')) {
  console.log(JSON.stringify(base));
  process.exit(0);
}
if (!process.env.TYPESAFE_API_KEY) throw new Error('TYPESAFE_API_KEY is required');
const output = option('--output');
await mkdir(output);
const envelope = { ...base, started_at: new Date().toISOString(), requested_model: study.prompt_config.model,
  model_revision: null, completed: false, rows: [] };
await writeFile(path.join(output, 'run.json'), JSON.stringify(envelope, null, 2) + '\n');
for (const item of plan) {
  const provider = new JevProvider({ id: 'baseline-v1', config: study.prompt_config });
  const summary = await evaluateBatch(item.state, [provider]);
  if (summary.results.length !== 1) throw new Error('Unexpected response count');
  const result = summary.results[0];
  envelope.rows.push({ repeat: item.repeat, arm: item.arm, candidate_id: item.candidate_id,
    context_sha256: item.context_sha256, response: result.response, error: result.error,
    received_at: new Date().toISOString() });
  envelope.completed = envelope.rows.length === plan.length;
  await writeFile(path.join(output, 'run.json'), JSON.stringify(envelope, null, 2) + '\n');
  console.log(`Global goal-profile experiment: ${envelope.rows.length}/${plan.length} responses saved`);
}
