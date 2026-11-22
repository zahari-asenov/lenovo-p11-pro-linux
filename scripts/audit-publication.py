#!/usr/bin/env python3
"""Read-only Git publication inventory; emit categories/paths, never matched values.

Gitleaks remains the secret scanner. This supplements it with reachable-blob
sizes, upstream fixture provenance and project-specific privacy indicators.
No files outside the Git object database and an explicitly supplied report
are read. The external historical archive is deliberately never traversed.
"""
import argparse
import collections
import json
import re
import subprocess
from pathlib import Path


def git(*args):
    return subprocess.check_output(['git', *args])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gitleaks-report', type=Path)
    parser.add_argument('--upstream-ref', default='public-upstream-fd78d179')
    parser.add_argument('--revision', action='append', metavar='REF',
                        help='Audit only ancestors of REF; repeat for multiple tips (default: all refs).')
    args = parser.parse_args()
    if args.revision:
        resolved = [git('rev-parse', '--verify', '--end-of-options',
                        f'{revision}^{{commit}}').decode().strip()
                    for revision in args.revision]
        revision_args = list(dict.fromkeys(resolved))
        refs = args.revision
        scope = {'mode': 'selected-revisions', 'requested': args.revision,
                 'resolved_commits': revision_args,
                 'includes_other_local_refs': False}
    else:
        revision_args = ['--all']
        refs = git('for-each-ref', '--format=%(refname)').decode().splitlines()
        scope = {'mode': 'all-refs', 'includes_other_local_refs': True}
    commits = set(git('rev-list', *revision_args).decode().splitlines())
    objects = {}
    for line in git('rev-list', '--objects', *revision_args).decode().splitlines():
        oid, _, path = line.partition(' ')
        objects.setdefault(oid, path)
    baseline = set(git('ls-tree', '-r', '--format=%(objectname)',
                       args.upstream_ref).decode().splitlines())
    sizes = subprocess.check_output(
        ['git', 'cat-file', '--batch-check=%(objectname) %(objecttype) %(objectsize)'],
        input=('\n'.join(objects) + '\n').encode()).decode().splitlines()
    blobs = {}
    for line in sizes:
        oid, kind, size = line.split()
        if oid in objects and kind == 'blob':
            blobs[oid] = int(size)
    risky_suffix = re.compile(r'(?:\.(?:img|ext4|bin|wmfw|deb|p12|pfx|pem|key|gz|zip|tar|tgz|xz|zst|cpio|dtb|pcap|pcapng|sqlite3?|db)|(?:^|/)(?:id_(?:rsa|ed25519)|\.env))$', re.I)
    patterns = {
        'personal_home_path': re.compile(rb'/home/(?!root(?:/|\b))[A-Za-z0-9_.-]+/'),
        'device_serial_field': re.compile(rb'(?:androidboot\.serialno=|fastboot\s+-s\s+)[A-Za-z0-9]{6,}'),
        'private_ipv4': re.compile(rb'\b(?:192\.168\.[0-9]{1,3}\.[0-9]{1,3}|10\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}|172\.(?:1[6-9]|2[0-9]|3[01])\.[0-9]{1,3}\.[0-9]{1,3})\b'),
        'private_key_header': re.compile(rb'-----BEGIN (?:OPENSSH |RSA |EC |DSA |ENCRYPTED )?PRIVATE KEY-----'),
        'email_address': re.compile(rb'\b[A-Za-z0-9_.+%-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
    }
    indicators = collections.defaultdict(list)
    counts = collections.Counter()
    project_binary_blobs = []
    proc = subprocess.Popen(['git', 'cat-file', '--batch'], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE)
    try:
        for oid in blobs:
            if oid in baseline:
                continue
            proc.stdin.write((oid + '\n').encode())
            proc.stdin.flush()
            header = proc.stdout.readline().split()
            content = proc.stdout.read(int(header[2]))
            assert proc.stdout.read(1) == b'\n'
            if b'\0' in content:
                project_binary_blobs.append({'path': objects[oid], 'blob': oid,
                                             'bytes': len(content)})
            for category, regex in patterns.items():
                matches = len(regex.findall(content))
                if matches:
                    counts[category] += matches
                    indicators[category].append({'path': objects[oid],
                                                 'blob': oid, 'count': matches})
    finally:
        proc.stdin.close()
        proc.stdout.close()
        proc.wait()
    findings = []
    if args.gitleaks_report:
        for finding in json.loads(args.gitleaks_report.read_text()):
            path = finding.get('File', '')
            commit = finding.get('Commit', '')
            if commit not in commits:
                parser.error('Gitleaks report contains a finding outside the selected audit history; use a scope-matched report.')
            try:
                oid = git('rev-parse', f'{commit}:{path}').decode().strip()
                upstream = oid in baseline
            except subprocess.CalledProcessError:
                upstream = False
            findings.append({'rule': finding.get('RuleID'), 'path': path,
                             'line': finding.get('StartLine'), 'commit': commit,
                             'identical_upstream_blob': upstream})
    identity_fields = git('log', *revision_args, '--format=%aN%x00%aE%x00%cN%x00%cE').replace(b'\n', b'\0').split(b'\0')
    commit_messages = git('log', *revision_args, '--format=%B')
    result = {
        'head': git('rev-parse', 'HEAD').decode().strip(), 'refs': refs,
        'scope': scope, 'reachable_commits': len(commits),
        'reachable_blobs': len(blobs), 'reachable_blob_bytes': sum(blobs.values()),
        'project_blobs_privacy_scanned': sum(oid not in baseline for oid in blobs),
        'author_committer_distinct_identity_fields': len(set(x for x in identity_fields if x)),
        'commit_message_privacy_indicators': {category: len(regex.findall(commit_messages))
                                              for category, regex in patterns.items()},
        'upstream_reference': args.upstream_ref,
        'large_blobs_over_50MiB': [{'path': objects[oid], 'blob': oid, 'bytes': size}
                                 for oid, size in blobs.items() if size > 50 * 1024**2],
        'largest_blobs': [{'path': objects[oid], 'bytes': size}
                         for oid, size in sorted(blobs.items(), key=lambda pair: pair[1], reverse=True)[:5]],
        'artifact_or_key_paths': [{'path': objects[oid], 'bytes': size,
                                  'identical_upstream_blob': oid in baseline}
                                 for oid, size in blobs.items()
                                 if risky_suffix.search(objects[oid])],
        'privacy_indicator_occurrences': dict(counts),
        'project_binary_blobs': project_binary_blobs,
        'privacy_indicator_blobs': dict(indicators),
        'gitleaks_findings': findings,
        'limits': ['Indicators are not confirmed secrets.',
                   'Privacy regexes cover project blobs, excluding byte-identical upstream blobs.',
                   'Gitleaks report coverage and exclusions require separate review.',
                   'Untracked files, reflogs and unreachable objects are not publication refs.',
                   'No external archive or device filesystem was read.'],
    }
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
