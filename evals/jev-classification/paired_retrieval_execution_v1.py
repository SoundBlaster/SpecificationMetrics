"""Bounded transport wrapper preserving exact successful HTTP response bodies."""
import argparse
import base64
import json
from pathlib import Path

import coreinfra_retry_run as transport
from coreinfra_transport import post
from decision_choice_contract_v2 import ChoiceContractError, ResponseIdentityError
from paired_retrieval_study_v1 import STUDY, source_digests, verify
from retrieval_fact_adapter_v1 import producer_digests as adapter_inventory
from retrieval_fact_adapter_v1.native import parse_response
from retrieval_index_v1.source import encoded


def execute(preparation, run, *, live=False, sender=post):
    manifest = verify(preparation)
    if (run / 'manifest.json').read_bytes() != (preparation / 'manifest.json').read_bytes():
        raise ValueError('execution manifest differs from preparation')
    if not live:
        return transport.execute(run, live=False)
    if any((run / n).exists() for n in (*transport.OUTPUTS, 'execution-binding.json')):
        raise ValueError('refuse to repeat or overwrite a run')
    inventory = adapter_inventory()
    source_inventory = source_digests()
    pending = iter(manifest['requests'])

    def capture(endpoint, wire, key, **kwargs):
        request = next(pending)
        if endpoint != request['endpoint'] or wire != request['wire_json'].encode():
            raise ValueError('sender request differs from schedule')
        if source_digests() != source_inventory:
            raise ValueError('study source changed during execution')
        result = sender(endpoint, wire, key, **kwargs)
        raw = result.get('body')
        if result['status'] == 'http_response' and result['http_status'] == 200 and isinstance(raw, bytes):
            result['raw_body_sha256'] = transport.sha(raw)
            try:
                body = transport.decode(raw)
                if isinstance(body, dict):
                    result['raw_body_base64'] = base64.b64encode(raw).decode('ascii')
                    try:
                        parse_response(raw, provider=request['provider'], model=request['requested_model'])
                    except ResponseIdentityError as error:
                        # The existing runner stops after any non-json_received
                        # status. Keep exact JSON bytes while stopping attribution.
                        result.update(status='native_identity_error', native_rejection_code=error.code)
                    except ChoiceContractError:
                        pass  # Record native invalidity later without retrying inference.
            except (ValueError, UnicodeError):
                pass
        return result

    try:
        return transport.execute(run, live=True, sender=capture)
    finally:
        if (run / 'receipt.json').is_file():
            files = {name: transport.sha((run / name).read_bytes()) for name in transport.OUTPUTS
                     if (run / name).is_file()}
            binding = dict(study=STUDY, status='local_execution_snapshot_not_remote_attestation',
                           manifest_sha256=transport.sha((run / 'manifest.json').read_bytes()),
                           file_sha256=files, study_source_digests=source_inventory,
                           adapter_runtime_inventory=inventory,
                           producers_unchanged=(source_digests() == source_inventory
                                                and adapter_inventory() == inventory))
            with (run / 'execution-binding.json').open('x') as stream:
                stream.write(encoded(binding) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparation', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    print(json.dumps(execute(args.preparation, args.run, live=args.live), indent=2))


if __name__ == '__main__':
    main()
