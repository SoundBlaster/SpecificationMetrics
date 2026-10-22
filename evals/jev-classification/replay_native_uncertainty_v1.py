"""Compare a new shadow policy with the spent PR714 run; zero hosted inference."""
import argparse
from pathlib import Path

import native_uncertainty_v1 as policy
import specgraph_pr714_live_v1 as live
from retrieval_fact_adapter_v1.dependencies import local_closure
from structured_semantic_review_v1.preparation import encoded, sha

ROOT = Path(__file__).resolve().parent
CONTRACT = ROOT.parent.parent / 'docs/native-uncertainty-routing-v1.md'


def producers():
    files = local_closure(ROOT, [Path(__file__).resolve()])
    return {str(p.relative_to(ROOT.parent.parent)): sha(p.read_bytes()) for p in files + [CONTRACT]}


def compare():
    # Preserve the original local runtime qualification and complete inventory.
    # This is not a new portable verifier for the historical live experiment.
    live.verify_result()
    manifest = live.read(live.RUN / 'manifest.json')
    rows = []
    for request in manifest['requests']:
        if request['kind'] != 'jev':
            continue
        observed, raw = live.capture(live.RUN / request['id'])
        row = policy.evaluate(live.bound_task(request['case']), raw,
                              http_status=observed['http_status'] or 200)
        rows.append(dict(case=request['case'], **row))
    return dict(policy=policy.POLICY, mode='offline_shadow',
        source_result_receipt_sha256=sha((live.RUN / 'result-receipt.json').read_bytes()),
        original_selected_reviews=live.read(live.RUN / 'report.json')['selected_reviews'],
        shadow_selected_reviews=sum(row['route'] == 'ordinary_review' for row in rows),
        reused_captures=len(rows), hosted_requests=0, review_execution='not_run',
        automatic_fact_acceptance=False, metric_effect='none', semantic_accuracy=None, cases=rows)


def render(report):
    lines = ['# Native uncertainty routing · offline shadow v1', '',
             'Four preserved Jev responses; zero new hosted requests. Luna review was not run.', '',
             '| Case | Baseline | Shadow | Axes without strict majority |',
             '| --- | --- | --- | --- |']
    for row in report['cases']:
        weak = ', '.join(a['axis'] for a in row['axes'] if not a['strict_majority']) or 'none'
        lines.append(f"| {row['case']} | {row['baseline_route']} | {row['route']} | {weak} |")
    lines.extend(['', 'This is a post-observation policy diagnostic, not independent quality validation.',
                  'Native confidence remains recorded metadata; no calibrated confidence claim or threshold.',
                  'Original reports, prompts, paid-run reservation and accepted facts remain unchanged.', ''])
    return '\n'.join(lines)


def save(output):
    report = compare()
    output.mkdir(exist_ok=False)
    live.write(output / 'comparison.json', report)
    (output / 'README.md').write_text(render(report), encoding='utf-8')
    live.write(output / 'receipt.json', dict(policy=policy.POLICY, producer_sha256=producers(),
        files_sha256={p.name: sha(p.read_bytes()) for p in sorted(output.iterdir())}))
    return report


def verify(output):
    report = compare()
    receipt = live.read(output / 'receipt.json')
    live.check(receipt == dict(policy=policy.POLICY, producer_sha256=producers(), files_sha256={
        p.name: sha(p.read_bytes()) for p in output.iterdir() if p.name != 'receipt.json'}),
        'shadow receipt differs')
    live.check(live.read(output / 'comparison.json') == report
               and (output / 'README.md').read_text() == render(report), 'shadow comparison differs')
    return dict(verified=True, hosted_requests=0, shadow_selected_reviews=report['shadow_selected_reviews'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--write', type=Path)
    action.add_argument('--verify', type=Path)
    args = parser.parse_args()
    result = save(args.write) if args.write else verify(args.verify) if args.verify else compare()
    print(encoded(result))
