"""Deterministic Markdown for an informational, revision-bound semantic review."""
import re
from urllib.parse import quote


def cell(value):
    text = str('unknown' if value is None else value).replace('\r', ' ').replace('\n', ' ').replace('|', '&#124;').replace('`', '&#96;')
    return '`' + text.replace('<', '&lt;').replace('>', '&gt;') + '`'


def fenced(value):
    text = str(value)
    fence = '`' * max(3, 1 + max((len(s) for s in re.findall(r'`+', text)), default=0))
    return fence + '\n' + text + ('\n' if not text.endswith('\n') else '') + fence


def render(report):
    review, receipt = report['inspection'], report['transport']
    binding = review['original_route']['binding']
    url = ('https://github.com/' + quote(binding['repository'], safe='/') + '/blob/'
           + quote(binding['revision'], safe='') + '/' + quote(binding['path'], safe='/')
           + '#L' + str(binding['start_line']) + '-L' + str(binding['end_line']))
    result = review.get('review')
    labels = result['labels'] if result else None
    lines = ['# Semantic review · informational', '',
        '**Status:** ' + cell(review['status']) + ' · review ' + cell(review['review_status']), '',
        'Historical SpecGraph evidence view; this is not a review of the current main branch or a new merge gate.', '',
        '- Repository: ' + cell(binding['repository']),
        '- Source revision: ' + cell(binding['revision']),
        '- Decision: ' + cell(binding['decision_id']),
        '- Source: [' + cell(binding['path'] + ':' + str(binding['start_line']) + '–'
          + str(binding['end_line'])) + '](' + url + ')',
        '- Decision binding: ' + cell(review['decision_binding_sha256']),
        '- Review task: ' + cell(review['task_sha256']),
        '- Request: ' + cell(review['request_sha256']),
        '- Response: ' + cell(review['response_sha256'] or 'unavailable'), '',
        '## Classifications', '', '| Axis | Jev | Ordinary Luna |', '| --- | --- | --- |']
    for axis in ('concern_kind', 'evidence_confidence', 'ownership', 'tool_responsibility'):
        lines.append('| ' + cell(axis) + ' | ' + cell(review['original_assessment']['labels'][axis])
                     + ' | ' + cell(labels[axis] if labels else 'unavailable') + ' |')
    lines += ['', 'Unknown ownership/tool labels do not prove absence.', '', '## Review checks', '',
        '- Quote spans matched supplied excerpts: ' + cell(review['source_locators_verified']),
        '- Required citation coverage: ' + cell(review['required_citation_coverage_verified']),
        '- Semantic correctness verified: ' + cell(review['semantic_correctness_verified']), '']
    for finding in review['findings']:
        lines.append('- ' + cell(finding['reason']) + ': ' + cell(', '.join(finding.get('details', [])) or 'see status'))
    if not review['findings']:
        lines.append('All declared advisory resolution checks passed. This is not human acceptance or semantic proof.')
    lines += ['', '### Missing evidence', '']
    for gap in review['preserved_missing_evidence']:
        lines.append('- ' + cell(gap['id']) + ': ' + cell(gap['description']))
    if not review['preserved_missing_evidence']:
        lines.append('None reported.' if result else 'Unavailable: no complete structured review.')
    if result:
        lines += ['', '### Model rationale · unverified', '', fenced(result['rationale']), '', '### Proposed citations', '']
        bad = {int(i) for f in review['findings'] if f['reason'] == 'invalid_citations' for i in f['details']}
        for index, citation in enumerate(result['citations']):
            lines += ['- ' + cell(citation['axis']) + ' · ' + cell(citation['fragment_id']) + ' · lines '
                      + cell(str(citation['start_line']) + '–' + str(citation['end_line']))
                      + ' · ' + ('invalid quote/span' if index in bad else 'matched supplied excerpt'), '',
                      fenced(citation['quote']), '']
    usage = review.get('reported_usage')
    usage = usage if isinstance(usage, dict) else {}
    lines += ['', '## Transport and usage', '',
        '- Logical reviews attempted: ' + cell(receipt['attempted_requests']),
        '- Network attempts: ' + cell(receipt['network_attempts']),
        '- Potentially billable POSTs: ' + cell(receipt['potentially_billable_posts']),
        '- Ambiguous POSTs: ' + cell(receipt['ambiguous_posts']),
        '- Automatic retries: ' + cell(0),
        '- HTTP status: ' + cell(report['http_status']),
        '- Transport stop reason: ' + cell(receipt.get('stop_reason')),
        '- Returned model: ' + cell(review.get('returned_model') or 'unavailable'),
        '- HTTP call timing (seconds): ' + cell(receipt.get('http_elapsed_seconds')),
        '- Reported input tokens: ' + cell(usage.get('input_tokens', 'unknown')),
        '- Reported output tokens: ' + cell(usage.get('output_tokens', 'unknown')),
        '- Billed monetary cost: ' + cell('unknown'), '',
        'Timing covers the HTTP operation. Provider usage is metadata; reasoning tokens, when supplied, '
        'are part of output rather than an extra output count. Cache categories are retained in report.json.', '',
        'Transport evidence is a local TLS/dispatch capture, not remote execution attestation. '
        'The standalone inspector keeps transport_verified=false; the enclosing run binds the local receipt.', '',
        'No accepted facts, S/U, source code or merge gates were changed. No GitHub comment was posted by this runner.', '']
    return '\n'.join(lines)
