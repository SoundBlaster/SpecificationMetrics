"""Parent integration audit for a completed scope-v3.1 run; no inference/writes."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path('/Users/egor/Development/GitHub/0AL/.worktrees/specmetrics-rustjev-evaluation/evals/jev-classification')
sys.path.insert(0, str(ROOT))
import validate_scope_binding_annotations as validator
import prepare_scope_binding_v3_1 as preparation

run = ROOT / 'runs/2026-10-14-scope-binding-v3-1-results-astra-high'
sha = lambda raw: hashlib.sha256(raw).hexdigest()
checksums = {}
for line in (run / 'SHA256SUMS').read_text().splitlines():
    expected, name = line.split('  ', 1)
    path = (run / name).resolve()
    assert path.is_relative_to(run.resolve()), name
    assert name not in checksums, name
    assert sha(path.read_bytes()) == expected, name
    checksums[name] = expected
actual = {str(p.relative_to(run)) for p in run.rglob('*') if p.is_file() and p != run / 'SHA256SUMS'}
assert set(checksums) == actual, (set(checksums) ^ actual)
outputs = preparation.verify()
plan = {a['slot']: a for a in outputs['dispatch-plan.json']['assignments']}
receipts, rows, raw_by_slot = {}, {}, {}
for path in sorted((run / 'attempt-receipts').glob('*.json')):
    receipt = json.loads(path.read_text())
    if receipt.get('slot') not in plan:
        continue
    slot = receipt['slot']
    # This audit is for one retained valid attempt per slot; preserve any failures separately.
    assert slot not in receipts, ('multiple receipts for slot; inspect execution ledger first', slot)
    assert Path(receipt['directory']).resolve().is_relative_to(run.resolve())
    for delivered in receipt['delivered_files'].values():
        assert Path(delivered).resolve().is_relative_to(run.resolve())
    candidates = [p for p in (run / 'raw-attempts').rglob('annotations.json')
                  if sha(p.read_bytes()) == receipt['raw_output_sha256']]
    assert len(candidates) == 1, (slot, candidates)
    raw = candidates[0].read_bytes()
    result = validator.validate_attempt(preparation.RUN, receipt, raw)
    assert result['annotated_cases'] == 4
    assert result['scope_semantic_fidelity_verified'] is False
    receipts[slot] = receipt
    raw_by_slot[slot] = sha(raw)
    rows[slot] = {r['case_id']: r for r in json.loads(raw)['annotations']}
assert len(receipts) == 12
assert len({r['agent_task'] for r in receipts.values()}) == 12
review = json.loads((run / 'review' / 'semantic-review.json').read_text())
assert review['human_gold'] is False
assert review['metric_effect'] == 'none'
expected_keys = {(a['slot'], c['case_id']) for a in plan.values() for c in a['cases']}
judgments = 0
for name in ('scope_fidelity', 'role_witness', 'ownership'):
    entries = review['criteria'][name]['entries']
    keys = [(e['slot'], e['case_id']) for e in entries]
    assert len(keys) == 48 and set(keys) == expected_keys
    for entry in entries:
        slot, cid = entry['slot'], entry['case_id']
        row = rows[slot][cid]
        assert entry['raw_output_sha256'] == raw_by_slot[slot]
        for field in ('scope_unit', 'scope_binding_sha256', 'task_sha256', 'state_sha256', 'rubric_sha256'):
            assert entry[field] == row[field], (name, slot, cid, field)
        assert entry['criterion_met'] is None or type(entry['criterion_met']) is bool
        assert isinstance(entry['review_note'], str) and entry['review_note'].strip()
        for axis in validator.AXES:
            quote = entry['rationale_quotes'][axis]
            assert isinstance(quote, str) and quote.strip() and quote in row['rationales'][axis], (name, slot, cid, axis)
        judgments += 1
print('Parent audit passed:',len(checksums),'checksums; 12 unique contexts; 48 rows;',judgments,'exact review bindings')
for cid in ('target-01', 'target-02', 'target-03', 'target-04'):
    for cell in ('01', '02', '03', '04'):
        assigned = [(slot, cid) for slot, a in plan.items() if any(c['case_id'] == cid and c['cell'] == cell for c in a['cases'])]
        print(cid, cell, {axis: dict(Counter(rows[slot][case_id][axis] for slot, case_id in assigned)) for axis in validator.AXES})
