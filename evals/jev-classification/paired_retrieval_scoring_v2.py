"""Operational scoring consumer v2; preserve partial diagnostics, no new H1/H2 authority."""
import argparse
import json
from pathlib import Path

import paired_retrieval_scoring_v1 as original
from coreinfra_retry_run import decode, sha
from retrieval_index_v1.source import encoded
from verify_paired_retrieval_transport_v2 import inspect

CONTRACT = 'specmetrics.paired-retrieval-scoring/v2'


def score(run):
    contract = original.verify_contract()
    qualification = original.qualify_reference(original.QUALIFICATION)
    manifest = original.verify_preparation(original.PREPARATION)
    transport = inspect(original.PREPARATION, run)
    original.require(qualification['paired_quality_scoring_allowed'] is False,
                     'v2 does not upgrade the reference qualification')
    references = {(v['case_id'], v['arm']): v['labels']
                  for v in decode((original.ANNOTATIONS / 'reference.json').read_bytes())['views']}
    complete = transport['transport_verified'] is True
    if not complete:
        h3 = 'fails_incomplete_execution' if transport.get('stop_reason') else 'not_evaluable_incomplete_evidence'
    else:
        h3 = ('passes_pilot' if transport['operationally_complete'] and transport['native_contract_valid']
              else 'fails_ambiguity_or_native_contract')
    return dict(contract=CONTRACT, original_contract_sha256=sha((original.FROZEN / 'contract.json').read_bytes()),
        reference_design_status=qualification['status'], paired_quality_scoring_allowed=False,
        transport_status=transport['status'], transport_evidence=transport,
        providers=original.summarize(transport.get('rows', []), manifest['requests'], references, qualified=False),
        H3=dict(status=h3, planned_responses=contract['planned_responses'],
                reserved_max_network_attempts=contract['reserved_max_network_attempts']),
        interpretation='verified_prefix_diagnostics_are_not_complete_cohort_or_quality_evidence',
        inference_authorized=False, metric_effect='none')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = score(args.run)
    with args.output.open('x') as output:
        output.write(encoded(result) + '\n')
    print(json.dumps(dict(status=result['transport_status'], H3=result['H3'])))
