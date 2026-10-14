"""Retain freeze v1 and correct an overstatement of row independence in prose."""
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parent
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
history=ROOT/'freeze-revisions'/'v1'
history.mkdir(parents=True,exist_ok=False)
for name in ('analysis/report.md','execution-receipt.json','SHA256SUMS'):
    src=ROOT/name
    with (history/src.name).open('xb') as stream: stream.write(src.read_bytes())
report=ROOT/'analysis'/'report.md'
old='Получены **48 независимых raw annotations: 12 fresh contexts × 4 разных families**.'
new='Получены **48 raw annotations из 12 fresh contexts; по 4 разных families в каждом**.\n+Четыре rows одного context не считаются статистически независимыми наблюдениями.'
text=report.read_text()
assert text.count(old)==1
report.write_text(text.replace(old,new))
rp=ROOT/'execution-receipt.json'
receipt=json.loads(rp.read_bytes())
receipt['frozen_at']=datetime.now(timezone.utc).isoformat()
receipt['freeze_revision']=2
receipt['previous_freeze']={
 'directory':'freeze-revisions/v1',
 'status':'superseded_before_ownership_handoff',
 'reason':'Correct report wording: 48 rows are nested in 12 contexts; no independent-row claim.',
 'previous_execution_receipt_sha256':sha(history/'execution-receipt.json'),
 'previous_sha256sums_sha256':sha(history/'SHA256SUMS'),
 'previous_report_sha256':sha(history/'report.md'),
 'raw_annotations_and_semantic_judgments_changed':False,
 'historical_manifest_note':'The v1 manifest describes the pre-correction root inventory; it is retained as history, not the active replay manifest.'}
receipt['analysis']['sha256']=sha(report)
receipt['analysis']['rows_nested_within_contexts']=True
receipt['analysis']['all_48_rows_statistically_independent_claimed']=False
receipt['artifact_file_sha256']={str(p.relative_to(ROOT)):sha(p) for p in sorted(ROOT.rglob('*'))
                                if p.is_file() and p not in (rp,ROOT/'SHA256SUMS')}
rp.write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n')
with (ROOT/'SHA256SUMS').open('w') as stream:
    for p in sorted(ROOT.rglob('*')):
        if p.is_file() and p != ROOT/'SHA256SUMS':
            stream.write(f'{sha(p)}  {p.relative_to(ROOT)}\n')
print(json.dumps({'status':'freeze_revision_2', 'execution_receipt_sha256':sha(rp),
                  'sha256sums_sha256':sha(ROOT/'SHA256SUMS')},indent=2))
