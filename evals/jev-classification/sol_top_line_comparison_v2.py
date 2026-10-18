"""Read-only comparison diagnostics with an explicit truncated-tail observation."""
import argparse
import json
from pathlib import Path

import sol_top_line_comparison_v1 as historical
from coreinfra_retry_run import decode, sha
from retrieval_index_v1.source import encoded
from verify_paired_retrieval_transport_v2 import inspect, read_prefix

CONTRACT = 'specmetrics.sol-top-line-comparison/v2'


def score(run):
    contract = historical.verify_contract()
    historical.check_binding(run)
    evidence = inspect(historical.PREPARATION, run)
    manifest = historical.verify_preparation(historical.PREPARATION)
    top_line = decode((historical.SOL_RUN / 'top-line.json').read_bytes())
    references = {(v['case_id'], v['arm']): v['labels'] for v in top_line['views']}
    path = run / 'responses.jsonl'
    captured, tail = read_prefix(path.read_bytes()) if path.exists() else ([], None)
    # Partial rows remain operational diagnostics; no complete-cohort agreement.
    rows = evidence.get('rows', []) if evidence['transport_verified'] is True else []
    return dict(contract=CONTRACT, original_contract_sha256=sha((historical.FROZEN / 'contract.json').read_bytes()),
        sol_top_line_sha256=contract['sol_top_line_sha256'], reference_authority=contract['reference_authority'],
        transport_evidence=evidence, captured_response_rows=len(captured), trailing_response_record=tail,
        captured_prefix_is_not_verified_without_complete_inspector_evidence=True,
        providers=historical.summarize(rows, manifest['requests'], references),
        semantic_accuracy=None, H1_H2_eligibility=False, automatic_fact_acceptance=False, metric_effect='none')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--score', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = score(args.score)
    with args.output.open('x') as output:
        output.write(encoded(report) + '\n')
    print(json.dumps(dict(contract=CONTRACT, captured_response_rows=report['captured_response_rows'],
                          trailing_response_record=report['trailing_response_record'])))
