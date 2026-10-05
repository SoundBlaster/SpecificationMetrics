import { evaluate } from 'promptfoo';

export async function evaluateBatch(context, providers) {
  const record = await evaluate({
    prompts: ['{{candidate_json}}'], providers,
    tests: [{ vars: { candidate_json: context } }],
  }, { cache: false, writeResults: false, maxConcurrency: 1 });
  return record.toEvaluateSummary();
}
