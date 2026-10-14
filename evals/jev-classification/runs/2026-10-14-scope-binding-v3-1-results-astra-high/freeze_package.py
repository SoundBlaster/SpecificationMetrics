"""One-time freeze of this result package; no annotation or semantic mutation."""
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parent
EVAL=ROOT.parent.parent
PREPARATION=EVAL/'runs'/'2026-10-14-scope-binding-preparation-v3-1'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_bytes())

assert not (ROOT/'execution-receipt.json').exists()
assert not (ROOT/'SHA256SUMS').exists()
attempts=read(ROOT/'analysis'/'attempt-identities.json')
review=read(ROOT/'review'/'semantic-review.json')
deps=[EVAL/name for name in (
    'prepare_scope_binding_v3_1.py','prepare_scope_binding_handoff.py',
    'validate_scope_binding_annotations.py','validate_manifest_contract_factorial.py',
    'prepare_scope_binding_diagnostic.py','prepare_manifest_contract_balanced.py',
    'prepare_manifest_contract_factorial.py','prepare_context_reference_v2.py',
    'question_grouping.py','scope-binding-handoff-runbook.md')]
deps += sorted(p for p in PREPARATION.iterdir() if p.is_file())
files=sorted(p for p in ROOT.rglob('*') if p.is_file())
assert not any('__pycache__' in p.parts for p in files)
receipt={
 'schema_version':1,'protocol':'scope-binding-v3.1',
 'status':'completed_bounded_annotation_run_with_proposed_nonblind_review',
 'run_directory':str(ROOT),'frozen_at':datetime.now(timezone.utc).isoformat(),
 'preparation_directory':str(PREPARATION),
 'preparation_receipt_sha256':sha(PREPARATION/'preparation-receipt.json'),
 'preparation_stage_dispatch_ready':False,
 'preparation_stage_note':'Frozen preparation stage is preserved; actual execution is recorded here.',
 'delivery_receipt_path':'delivery/delivery-receipt.json',
 'delivery_receipt_sha256':sha(ROOT/'delivery'/'delivery-receipt.json'),
 'implementation_file_sha256':{p.name:sha(p) for p in deps if p.parent==EVAL},
 'external_dependency_file_sha256':{str(p):sha(p) for p in deps},
 'artifact_file_sha256':{str(p.relative_to(ROOT)):sha(p) for p in files},
 'artifact_manifest_boundary':'All run files existing before this receipt; SHA256SUMS additionally binds this receipt. Neither digest file hashes itself.',
 'retained_attempts':attempts,'excluded_attempts':[],'failed_attempts':[],
 'counts':{'annotation_contexts_requested':12,'fresh_annotation_contexts_created':12,
           'replacement_contexts':0,'coordinator_model_integrator_contexts':1,
           'total_contexts_within_this_delegated_run':13,'valid_attempts':12,
           'retained_raw_attempts':12,'failed_attempts':0,'excluded_attempts':0,
           'annotation_rows':48,'distinct_families':4,'target_cells':16,
           'rows_per_target_cell':3,'semantic_judgments':144},
 'dispatch':{'waves':[['annotator-01','annotator-02','annotator-03','annotator-04'],
                      ['annotator-05','annotator-06','annotator-07','annotator-08'],
                      ['annotator-09','annotator-10','annotator-11','annotator-12']],
             'maximum_active_annotation_children':4,'context_inheritance':'none',
             'requested_model':'gpt-6-astra','requested_reasoning_effort':'high',
             'runtime_model_identity':None,'runtime_model_identity_verified':False,
             'exact_checked_prompt_dispatch':'Coordinator supplied each checked prompt text to spawn_agent; original tool transcript is dispatch evidence.',
             'fresh_context_task_ids_returned_by_tool':[a['agent_task'] for a in attempts],
             'before_each_spawn_actual_file_check':True,
             'preflight_capture_boundary':'Slot 01 parsed CLI result transcribed from pre-spawn tool output with explicit note; slots 02-12 are direct CLI stdout.',
             'replacement_limit':2,'replacement_reasons_allowed':['formal_invalid','incomplete','isolation_failure']},
 'formal_validation':{'all_12_attempts_passed':True,'all_48_scope_acknowledgments_verified':True,
                      'actual_declared_inputs_and_prompts_checked_before_dispatch_and_after_return':True,
                      'original_and_retained_raw_bytes_equal':True,
                      'package_audit_path':'validation/package-audit.json',
                      'semantic_correctness_verified':False},
 'review':{'path':'review/semantic-review.json','sha256':sha(ROOT/'review'/'semantic-review.json'),
           'role':'NONBLIND MODEL-INTEGRATOR','blind':False,'human':False,
           'proposed':True,'adjudication':False,'labels_changed':False,
           'criteria_counts':{k:v['counts'] for k,v in review['criteria'].items()},
           'needs_review_means':'Criterion support is not certified; no definitive incorrect raw label is established.',
           'automatic_batch_semantic_gate':False},
 'analysis':{'path':'analysis/report.md','sha256':sha(ROOT/'analysis'/'report.md'),
             'histograms_path':'analysis/histograms.json','histograms_sha256':sha(ROOT/'analysis'/'histograms.json'),
             'pooling_different_families':False,'decisive_coverage_denominator_per_axis_cell':3,
             'axis_cell_disagreements':5,'opportunity_abstentions':4,'concern_kind_abstentions':5,
             'target_cell_by_position_fully_crossed':False,
             'causal_order_or_model_mechanism_established':False},
 'isolation_boundary':{'enforcement':'scoped_assignment_and_fresh_context_and_self_report',
                      'filesystem_sandbox':False,'actual_model_consumption_verified':False,
                      'pre_post_checks_cannot_detect_restore_between_checks':True,
                      'replay_requires_original_declared_absolute_paths':True},
 'provider_requests':0,'provider_requests_definition':'Direct external Jev/Luna/provider API requests, excluding counted Codex annotation contexts.',
 'human_gold':False,'reference_frozen_for_provider_scoring':False,'metric_effect':'none',
 'production_classifier_changed':False,'raw_outcomes_edited':False,
 'historical_raw_annotations_or_author_labels_used_as_reference':False,
 'git_operations_performed_by_coordinator':False,
 'remaining_work':'Independent parent audit and focused PR; semantic questions remain proposed for review.'
}
with (ROOT/'execution-receipt.json').open('x') as stream:
    json.dump(receipt,stream,indent=2,ensure_ascii=False)
    stream.write('\n')
with (ROOT/'SHA256SUMS').open('x') as stream:
    for path in sorted(p for p in ROOT.rglob('*') if p.is_file() and p.name!='SHA256SUMS'):
        stream.write(f'{sha(path)}  {path.relative_to(ROOT)}\n')
print(json.dumps({'status':'package_frozen','execution_receipt_sha256':sha(ROOT/'execution-receipt.json'),
                  'sha256sums_sha256':sha(ROOT/'SHA256SUMS')},indent=2))
