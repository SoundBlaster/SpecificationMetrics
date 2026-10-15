"""Plan, update or check a revision-bound local retrieval index; no hosted API calls."""
import argparse
import json
import sqlite3
from pathlib import Path

from .local_model import LocalEncoder
from .source import snapshot
from .store import plan, read_current, update


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('plan', 'update', 'check'))
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--repository-id', required=True)
    parser.add_argument('--revision', default='HEAD')
    parser.add_argument('--include', action='append', required=True, help='fnmatch path glob; * includes /')
    parser.add_argument('--exclude', action='append', default=[])
    parser.add_argument('--store', type=Path, required=True)
    parser.add_argument('--model-path', type=Path, required=True, help='existing pinned local HF snapshot')
    parser.add_argument('--device', choices=('cpu', 'mps', 'cuda'), default='mps')
    args = parser.parse_args()
    source = snapshot(args.repo, args.repository_id, args.revision, args.include, args.exclude)
    encoder = LocalEncoder(args.model_path, args.device)
    if args.command == 'plan':
        result = plan(args.store, source, encoder.profile)
    elif args.command == 'update':
        result = update(args.store, source, encoder.profile, encoder)
    else:
        try:
            documents = read_current(args.store, source, encoder.profile)
        except (ValueError, sqlite3.DatabaseError) as error:
            print(json.dumps(dict(status='unavailable', reason=str(error))))
            return 2
        result = dict(status='current', revision=source['revision'], documents=len(documents),
                      authority='ranked_candidates_only')
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
