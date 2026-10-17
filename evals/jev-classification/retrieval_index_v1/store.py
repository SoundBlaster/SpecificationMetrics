"""One transactional active snapshot plus content-addressed vector cache."""
import json
import math
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .source import digest, encoded


@contextmanager
def connection(path, write=False):
    path = Path(path)
    if not write and not path.exists():
        yield None
        return
    db = sqlite3.connect(path if write else path.resolve().as_uri() + '?mode=ro', uri=not write, timeout=30)
    try:
        version = db.execute('PRAGMA user_version').fetchone()[0]
        if version == 0 and write:
            if db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
                raise ValueError('refuse an unrelated database')
            db.executescript('''
                CREATE TABLE vectors (key TEXT PRIMARY KEY, value TEXT NOT NULL, sha256 TEXT NOT NULL);
                CREATE TABLE active (singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                                     value TEXT NOT NULL, sha256 TEXT NOT NULL);
                PRAGMA user_version=1;
            ''')
        elif version != 1:
            raise ValueError('unsupported retrieval store version')
        if write:
            db.execute('BEGIN IMMEDIATE')
        else:
            db.execute('BEGIN')
        yield db
        if write:
            db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def active(db):
    row = db.execute('SELECT value, sha256 FROM active WHERE singleton=1').fetchone() if db else None
    if row is None:
        return None
    if digest(row[0]) != row[1]:
        raise ValueError('active manifest checksum differs')
    manifest = json.loads(row[0])
    if manifest.get('contract') != 'specmetrics.retrieval-index/v1' or manifest.get('status') != 'complete':
        raise ValueError('active manifest is not a complete supported snapshot')
    return manifest


def key(profile, text):
    return digest(encoded(dict(profile=profile, text=text)))


def valid_vector(values, dimension):
    if not isinstance(values, list) or len(values) != dimension:
        raise ValueError('embedding dimension differs')
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in values):
        raise ValueError('embedding contains invalid coordinates')
    if not math.isclose(sum(x*x for x in values), 1.0, rel_tol=1e-4, abs_tol=1e-4):
        raise ValueError('embedding must be normalized and nonzero')
    return values


def cached(db, cache_key, dimension):
    row = db.execute('SELECT value, sha256 FROM vectors WHERE key=?', (cache_key,)).fetchone() if db else None
    if row is None:
        return None
    if digest(row[0]) != row[1]:
        raise ValueError('cached embedding checksum differs')
    return valid_vector(json.loads(row[0]), dimension)


def validate_profile(profile):
    required = {'model', 'revision', 'dimensions', 'document_prompt', 'normalize', 'runtime', 'model_files_sha256'}
    if not required <= profile.keys() or profile['normalize'] is not True:
        raise ValueError('incomplete normalized encoder profile')
    if type(profile['dimensions']) is not int or profile['dimensions'] <= 0:
        raise ValueError('invalid dimensions')
    encoded(profile)  # Refuse non-JSON/NaN identities.


def prepare(db, source, profile):
    validate_profile(profile)
    old = active(db)
    if old and old['source']['repository_id'] != source['repository_id']:
        raise ValueError('store belongs to a different repository')
    identifiers = [d['id'] for d in source['documents']]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError('duplicate document IDs')
    current = {d['id']: key(profile, d['text']) for d in source['documents']}
    previous = old['keys'] if old else {}
    missing = {k: d['text'] for d in source['documents'] for k in [current[d['id']]]
               if cached(db, k, profile['dimensions']) is None}
    summary = dict(contract='specmetrics.retrieval-update/v1', revision=source['revision'],
                   documents=len(current), added=len(current.keys() - previous.keys()),
                   removed=len(previous.keys() - current.keys()),
                   changed=sum(current[k] != previous[k] for k in current.keys() & previous.keys()),
                   encode_inputs=len(missing), reused_documents=sum(k not in missing for k in current.values()),
                   profile_sha256=digest(encoded(profile)), source_sha256=digest(encoded(source)),
                   authority='ranked_candidates_only')
    return current, missing, summary


def plan(path, source, profile):
    with connection(path) as db:
        return dict(prepare(db, source, profile)[2], status='planned_not_published')


def update(path, source, profile, encode):
    """Serializes writers; failed encoding leaves the previous snapshot usable."""
    with connection(path, write=True) as db:
        keys, missing, report = prepare(db, source, profile)
        pending = list(missing)
        # Bounded batches; all writes and publication roll back on any failure.
        for offset in range(0, len(pending), 4):
            batch = pending[offset:offset + 4]
            vectors = encode([missing[k] for k in batch])
            if len(vectors) != len(batch):
                raise ValueError('encoder returned the wrong number of vectors')
            for cache_key, vector in zip(batch, vectors):
                raw = encoded(valid_vector(vector, profile['dimensions']))
                db.execute('INSERT INTO vectors VALUES (?, ?, ?)', (cache_key, raw, digest(raw)))
        manifest = dict(contract='specmetrics.retrieval-index/v1', status='complete',
                        source=source, profile=profile, keys=keys, report=report)
        raw = encoded(manifest)
        db.execute('INSERT OR REPLACE INTO active VALUES (1, ?, ?)', (raw, digest(raw)))
        return dict(report, status='complete', manifest_sha256=digest(raw))


def read_snapshot(path, expected_source, expected_profile):
    """Consumers must supply the desired revision/scope; stale data is never returned."""
    with connection(path) as db:
        manifest = active(db)
        if manifest is None:
            raise ValueError('index is missing')
        if manifest['source'] != expected_source or manifest['profile'] != expected_profile:
            raise ValueError('index is stale for the requested source, scope or encoder')
        result = []
        for doc in manifest['source']['documents']:
            cache_key = key(expected_profile, doc['text'])
            if manifest['keys'].get(doc['id']) != cache_key:
                raise ValueError('document-to-vector binding differs')
            vector = cached(db, cache_key, expected_profile['dimensions'])
            if vector is None:
                raise ValueError('active vector is missing')
            result.append(dict(doc, vector=vector))
        # Exclude update counters from content identity: a no-op refresh must not
        # change model context merely because vectors were reused this time.
        content = dict(source=expected_source, profile=expected_profile, documents=result)
        return dict(documents=result, content_sha256=digest(encoded(content)),
                    manifest_sha256=digest(encoded(manifest)))


def read_current(path, expected_source, expected_profile):
    return read_snapshot(path, expected_source, expected_profile)['documents']
