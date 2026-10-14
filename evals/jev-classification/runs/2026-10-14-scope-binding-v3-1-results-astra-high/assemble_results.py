"""Assemble this run's derived report and bind explicit model review data.

No labels are generated, adjudicated, repaired or inferred here. Semantic judgment
data are authored separately in review/manual_judgments.py; checks here are formal.
"""
import hashlib
import json
from pathlib import Path
import sys
from collections import Counter

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
EVAL = ROOT.parent.parent
sys.path.insert(0, str(EVAL))
sys.path.insert(0, str(ROOT / 'review'))
import validate_scope_binding_annotations as validator
import prepare_scope_binding_v3_1 as preparation
from manual_judgments import JUDGMENTS

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_bytes())
def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')

ledger = [json.loads(line) for line in (ROOT/'attempt-ledger.jsonl').read_text().splitlines()]
assert len(ledger) == 12 and all(e['disposition'] == 'retained_valid' for e in ledger)
assert len({e['agent_task'] for e in ledger}) == 12
rows, attempts, validations = [], [], []
for entry in sorted(ledger, key=lambda e:e['slot']):
    receipt = read(ROOT/entry['receipt_path'])
    raw_path = ROOT/entry['raw_path']
    raw = raw_path.read_bytes()
    check = validator.validate_attempt(preparation.RUN, receipt, raw)
    assert raw == Path(receipt['original_output_path']).read_bytes()
    preflight = read(ROOT/'validation'/f"{entry['attempt_id']}-preflight.json")
    assert preflight['status'] == 'scope_delivery_bytes_verified_not_dispatched'
    assert preflight['slot'] == entry['slot']
    prior = read(ROOT/'validation'/f"{entry['attempt_id']}-replay.stdout")
    assert check == prior
    validations.append({'attempt_id':entry['attempt_id'], 'receipt_path':entry['receipt_path'],
                        'receipt_sha256':sha(ROOT/entry['receipt_path']),
                        'raw_path':entry['raw_path'], 'raw_output_sha256':sha(raw_path),
                        'replay_result_path':f"validation/{entry['attempt_id']}-replay.stdout",
                        'replay_result_sha256':sha(ROOT/'validation'/f"{entry['attempt_id']}-replay.stdout"),
                        'scope_acknowledgments_verified':True, 'semantic_correctness_verified':False})
    attempts.append({**entry, 'context_inheritance':receipt['context_inheritance'],
                     'requested_model':receipt['requested_model'],
                     'requested_reasoning_effort':receipt['requested_reasoning_effort'],
                     'runtime_model_identity':None, 'runtime_model_identity_verified':False,
                     'delivered_files':receipt['delivered_files'],
                     'input_file_sha256':receipt['input_file_sha256'],
                     'dispatched_prompt_sha256':receipt['dispatched_prompt_sha256'],
                     'preflight_path':f"validation/{entry['attempt_id']}-preflight.json"})
    annotation = json.loads(raw)
    bindings = {b['case_id']:b for b in receipt['cases']}
    assert len(annotation['annotations']) == 4
    for row in annotation['annotations']:
        rows.append({**row, **bindings[row['case_id']], 'slot':entry['slot'],
                     'attempt_id':entry['attempt_id'], 'agent_task':entry['agent_task'],
                     'raw_path':entry['raw_path'], 'raw_output_sha256':sha(raw_path)})
assert len(rows) == 48
write(ROOT/'analysis'/'rows-with-identities.json', rows)
write(ROOT/'analysis'/'attempt-identities.json', attempts)

axes = {'opportunity':['eligible','excluded','needs_review'],
        'concern_kind':['policy','mechanics','variant_behavior','unknown']}
histograms, disagreements, abstentions = [], [], []
for target in [f'target-{i:02d}' for i in range(1,5)]:
    for cell in ['01','02','03','04']:
        members = [r for r in rows if r['case_id']==target and r['cell']==cell]
        assert len(members)==3
        summary = {'case_id':target, 'cell':cell, 'scope_unit':members[0]['scope_unit'],
                   'documents':cell in ('02','04'), 'axes':{}}
        for axis, labels in axes.items():
            counts = Counter(r[axis] for r in members)
            abstention_label = 'needs_review' if axis == 'opportunity' else 'unknown'
            identities = [{k:r[k] for k in ('slot','attempt_id','agent_task','raw_output_sha256','task_sha256','scope_binding_sha256','position')} | {'label':r[axis]} for r in members]
            summary['axes'][axis] = {'histogram':{label:counts[label] for label in labels},
                'decisive_coverage':{'numerator':3-counts[abstention_label], 'denominator':3},
                'agreement':len(counts)==1, 'members':identities}
            if len(counts)>1:
                disagreements.append({'case_id':target,'cell':cell,'axis':axis,'members':identities})
            for r in members:
                if r[axis] == abstention_label:
                    abstentions.append({k:r[k] for k in ('slot','case_id','cell','position','raw_output_sha256','task_sha256','scope_binding_sha256')} | {'axis':axis,'label':r[axis],'rationale':r['rationales'][axis], 'uncertainties':r['uncertainties']})
        histograms.append(summary)
write(ROOT/'analysis'/'histograms.json', {'status':'descriptive_not_adjudicated',
    'target_cells':histograms, 'disagreements':disagreements,'abstentions':abstentions,
    'pooling_across_families':False,'causal_order_effect_identified':False,
    'reference_frozen_for_provider_scoring':False,'human_gold':False,'metric_effect':'none'})

review = read(ROOT/'delivery'/'semantic-review.template.json')
review.update(status='proposed_nonblind_model_integrator_review_not_adjudication',
    reviewer={'agent_task':'/root/astra_scope_v3_1_run','role':'NONBLIND MODEL-INTEGRATOR',
              'requested_model':'gpt-6-astra','requested_reasoning_effort':'high',
              'runtime_model_identity':None,'runtime_model_identity_verified':False,
              'blind':False,'human':False},
    judgment_semantics={'criterion_met_true':'Reviewer proposes criterion is supported by this rationale and supplied case.',
                        'criterion_met_false':'Needs review: reviewer cannot certify sufficiency; not proof that the raw label is wrong.',
                        'quote_policy':'Full exact contiguous rationale paragraphs from both axes are retained per judgment.',
                        'no_automatic_semantic_grading':True,
                        'majority_or_formal_pass_used_as_semantic_rule':False})
by_key = {(r['slot'],r['case_id']):r for r in rows}
assert len(JUDGMENTS)==48
issues = []
for index, criterion in enumerate(('scope_fidelity','role_witness','ownership')):
    group=review['criteria'][criterion]
    for item in group['entries']:
        r=by_key[item['slot'],item['case_id']]
        decision=JUDGMENTS[(item['slot'][-2:],item['case_id'][-2:])]
        for key in ('scope_unit','state_sha256','task_sha256','rubric_sha256','scope_binding_sha256','cell','position'):
            assert item[key]==r[key]
        item.update(raw_output_sha256=r['raw_output_sha256'],
                    raw_path=r['raw_path'], agent_task=r['agent_task'],
                    criterion_met=decision[index],
                    judgment='met' if decision[index] else 'needs_review',
                    review_note=decision[index+3],
                    rationale_quotes={axis:r['rationales'][axis] for axis in axes})
        for axis, quote in item['rationale_quotes'].items():
            assert quote and quote in r['rationales'][axis]
        if not item['criterion_met']:
            issues.append({'criterion':criterion, **item})
    group.update(status='proposed_met' if all(e['criterion_met'] for e in group['entries']) else 'proposed_needs_review',
                 met=all(e['criterion_met'] for e in group['entries']),
                 counts={'met':sum(e['criterion_met'] for e in group['entries']),
                         'needs_review':sum(not e['criterion_met'] for e in group['entries'])})
review['formal_traceability'].update(status='12_attempts_formally_replayed_actual_files',validated_attempts=validations,
                                   runtime_identity_verified=False, consumption_verified=False)
write(ROOT/'review'/'semantic-review.json',review)
write(ROOT/'review'/'diagnosis.json', {'status':'proposed_nonblind_diagnosis_not_gold',
    'formal_failures':[], 'failed_attempts':[], 'excluded_attempts':[], 'replacements':0,
    'semantic_issues_requiring_review':issues,
    'definitive_incorrect_raw_labels_established':False,
    'lessons':['Formal scope acknowledgments and valid quotes do not prove role sufficiency.',
               'Shared utility versus application reference-integrity contract remains a substantive evidence question.',
               'Direct findings collection versus Specification evaluation role must be assessed from its argument, not majority vote.',
               'Agreement on all three mechanical exclusions in one cell does not settle correctness.'],
    'operational_notes':[{'event':'AGENTS.md lookup in worktree root failed','resolution':'Read supplied canonical /Users/egor/Development/GitHub/0AL/Platform/AGENTS.md; no experiment attempt affected.'},
                         {'event':'First preflight result was not shell-redirected','resolution':'Successful pre-spawn result retained as parsed transcription with explicit capture_note; tool transcript remains authoritative.'}],
    'outcomes_edited':False,'provider_requests':0,'metric_effect':'none'})
audit={'status':'formal_package_audit_passed_not_semantic_gate',
       'attempts':12,'rows':48,'fresh_annotation_contexts':12,'replacement_contexts':0,
       'unique_families_per_slot':4,'target_cells':16,'members_per_cell':3,
       'review_judgments':144,'rationale_quotes':288,'review_binding_checks':True,
       'delivery_original_paths_rechecked':True,'delivered_and_retained_raw_bytes_equal':True,
       'runtime_identity_verified':False,'model_input_consumption_verified':False,
       'semantic_correctness_verified':False,
       'review_counts':{k:v['counts'] for k,v in review['criteria'].items()},
       'axis_cell_disagreements':len(disagreements),'axis_abstentions':len(abstentions)}
write(ROOT/'validation'/'package-audit.json',audit)
print(json.dumps(audit,indent=2))
