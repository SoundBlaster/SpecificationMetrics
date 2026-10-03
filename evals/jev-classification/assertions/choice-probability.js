module.exports = (output, context) => {
  const axis = context.config.axis;
  const expectedKey = axis === 'opportunity'
    ? 'expected_opportunity'
    : 'expected_concern_kind';
  const expected = context.vars[expectedKey];
  const answer = output && output[axis];

  if (!answer || typeof answer.choice !== 'string') {
    return {
      pass: false,
      score: 0,
      reason: `Missing Jev Choice answer for ${axis}`,
    };
  }

  const probability = answer.probabilities?.[expected] ?? 0;
  return {
    pass: answer.choice === expected,
    score: probability,
    reason: `expected=${expected}; actual=${answer.choice}; expected_label_probability=${probability}; label_status=${context.vars.label_status}`,
  };
};
