"""Read-only byte, identity and quote replay; never grades semantic correctness."""
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
EVAL=ROOT.parent.parent
sys.path.insert(0,str(EVAL))
import validate_scope_binding_annotations as validator
import prepare_scope_binding_v3_1 as preparation
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_bytes())
manifest={}
for line in (ROOT/'SHA256SUMS').read_text().splitlines():
    digest,name=line.split('  ',1)
    assert sha(ROOT/name)==digest, name
    manifest[name]=digest
actual={str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.is_file() and p != ROOT/'SHA256SUMS'}
assert set(manifest)==actual, 'Package file inventory differs'
execution=read(ROOT/'execution-receipt.json')
for name,digest in execution['artifact_file_sha256'].items(): assert sha(ROOT/name)==digest,name
for name,digest in execution['external_dependency_file_sha256'].items(): assert sha(Path(name))==digest,name
rows={}
for entry in execution['retained_attempts']:
    receipt=read(ROOT/entry['receipt_path'])
    raw_path=ROOT/entry['raw_path']
    result=validator.validate_attempt(preparation.RUN,receipt,raw_path.read_bytes())
    assert result==read(ROOT/'validation'/f"{entry['attempt_id']}-replay.stdout")
    assert raw_path.read_bytes()==Path(receipt['original_output_path']).read_bytes()
    for row in read(raw_path)['annotations']:
        rows[receipt['slot'],row['case_id']]={**row,'raw_output_sha256':sha(raw_path)}
review=read(ROOT/'review'/'semantic-review.json')
n=0
for group in review['criteria'].values():
    assert len(group['entries'])==48
    for e in group['entries']:
        r=rows[e['slot'],e['case_id']]
        for k in ('state_sha256','task_sha256','rubric_sha256','scope_unit','scope_binding_sha256','raw_output_sha256'):
            assert e[k]==r[k]
        for axis,q in e['rationale_quotes'].items(): assert q and q in r['rationales'][axis]
        assert type(e['criterion_met']) is bool and e['review_note']
        n+=1
assert len(rows)==48 and n==144
assert len(execution['retained_attempts'])==12
print(json.dumps({'status':'formal_replay_passed_not_semantic_gate','files':len(manifest),
                  'attempts':12,'rows':48,'review_judgments':n,
                  'original_paths_verified':True,'semantic_correctness_verified':False,
                  'runtime_identity_verified':False,'provider_requests':0},indent=2))
