"""Offline native fact-response adaptation; never reads credentials or sends requests."""
import argparse
import json
from pathlib import Path

from prepare_retrieval_context_v1 import PROVIDERS
from retrieval_fact_adapter_v1 import adapt_response
from retrieval_fact_adapter_v1.native import MAX_RESPONSE_BYTES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparation', type=Path, required=True)
    parser.add_argument('--provider', choices=sorted(PROVIDERS), required=True)
    parser.add_argument('--response', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='new adaptation report file')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output must be a new file')
    with args.response.open('rb') as stream:
        raw = stream.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        parser.error('response exceeds 1 MiB; refusing a partial snapshot')
    report = adapt_response(args.preparation, args.provider, raw)
    report['response_file'] = str(args.response)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(status=report['status'], provider=args.provider,
                          native_status=report['native_status'], output=str(args.output)), ensure_ascii=False))
    return 0 if report['status'] == 'proposed_not_accepted' else 2


if __name__ == '__main__':
    raise SystemExit(main())
