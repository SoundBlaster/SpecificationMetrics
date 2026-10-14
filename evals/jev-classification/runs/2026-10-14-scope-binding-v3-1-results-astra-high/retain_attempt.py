"""Run-local exact-byte retention and formal replay; does not change annotations."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
EVAL = ROOT.parent.parent
def sha(raw): return hashlib.sha256(raw).hexdigest()
def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')

for number in sys.argv[1:]:
    slot = f'annotator-{int(number):02d}'
    attempt = slot + '-attempt-01'
    source = ROOT / 'delivery' / slot / 'annotations.json'
    raw = source.read_bytes()
    folder = ROOT / 'raw-attempts' / attempt
    folder.mkdir(exist_ok=False)
    retained = folder / 'annotations.json'
    with retained.open('xb') as stream: stream.write(raw)
    receipt = json.loads((ROOT / 'delivery' / 'receipts' / (slot + '.json')).read_bytes())
    receipt.update(agent_task=f'/root/astra_scope_v3_1_run/annotator_{int(number):02d}', context_inheritance='none',
                   requested_model='gpt-6-astra', requested_reasoning_effort='high',
                   runtime_model_identity=None, runtime_model_identity_verified=False,
                   raw_output_sha256=sha(raw), attempt_id=attempt,
                   raw_output_path=str(retained), original_output_path=str(source),
                   retained_at=datetime.now(timezone.utc).isoformat())
    rp = ROOT / 'attempt-receipts' / (attempt + '.json')
    save(rp, receipt)
    command = [str(EVAL.parent.parent / '.venv/bin/python'), 'validate_scope_binding_annotations.py',
               '--assignment', str(rp), '--annotation', str(retained)]
    result = subprocess.run(command, cwd=EVAL, capture_output=True)
    (ROOT / 'validation' / (attempt + '-replay.stdout')).write_bytes(result.stdout)
    (ROOT / 'validation' / (attempt + '-replay.stderr')).write_bytes(result.stderr)
    entry = dict(attempt_id=attempt, slot=slot, agent_task=receipt['agent_task'],
                 raw_output_sha256=sha(raw), raw_path=str(retained.relative_to(ROOT)),
                 receipt_path=str(rp.relative_to(ROOT)), validation_exit_code=result.returncode,
                 disposition='retained_valid' if result.returncode == 0 else 'retained_failed',
                 error=result.stderr.decode(), replacements=0)
    with (ROOT / 'attempt-ledger.jsonl').open('a') as stream:
        stream.write(json.dumps(entry) + '\n')
    print(json.dumps(entry))
