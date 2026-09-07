#!/usr/bin/env python3
"""Reject common private files and credentials without printing their contents."""
import argparse
import pathlib
import re
import subprocess
import sys

UPSTREAM_BASE = 'fb6de8fb9bce04cb7c37454c08e143df7923b53e'
RULES = {
    'private key': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
    'GitHub token': re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})'),
    'AWS access key': re.compile(rb'AKIA[0-9A-Z]{16}'),
    'Slack token': re.compile(rb'xox[baprs]-[A-Za-z0-9-]{20,}'),
    'database credentials': re.compile(rb'(?:mongodb(?:\+srv)?|postgres(?:ql)?|redis)://[^\s/\"\x27:]+:[^\s/@\"\x27]+@'),
    'Habitica API token': re.compile(rb'[\"\x27]api_?token[\"\x27]\s*:\s*[\"\x27][0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}[\"\x27]', re.IGNORECASE),
    'stored password hash': re.compile(rb'\$2[aby]\$[0-9]{2}\$[./A-Za-z0-9]{53}'),
}


def git(*args):
    return subprocess.check_output(['git', *args], stderr=subprocess.DEVNULL)


def private_path(name):
    path = pathlib.PurePosixPath(name)
    leaf = path.name.lower()
    parts = {part.lower() for part in path.parts}
    if leaf.endswith(('.example', '.sample', '.template')):
        return False
    return bool(
        parts & {'work', 'backups', 'backup', '.ssh', 'mongodb-data', 'mongo-data', 'secrets'}
        or leaf in {'.habitica-server.json', 'config.json', 'credentials.json', 'service-account.json', 'id_rsa', 'id_ed25519'}
        or leaf == '.env' or leaf.startswith('.env.')
        or leaf.startswith(('wiredtiger', 'mongodump'))
        or leaf.endswith(('.pem', '.key', '.p12', '.pfx', '.bson', '.sqlite', '.sqlite3', '.db', '.dump', '.dump.gz', '.archive', '.archive.gz', '.sql', '.sql.gz'))
    )


def content_rules(data):
    return [name for name, regex in RULES.items() if regex.search(data)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--history', action='store_true', help='Also scan personal commit additions since the public upstream baseline')
    args = parser.parse_args()
    failures = set()
    entries = git('ls-files', '--stage', '-z').split(b'\0')
    personal_paths = set(git('diff', '--cached', '--name-only', '-z', UPSTREAM_BASE).split(b'\0'))
    reader = subprocess.Popen(['git', 'cat-file', '--batch'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    for entry in entries:
        if not entry:
            continue
        metadata, raw_name = entry.split(b'\t', 1)
        mode, oid, stage = metadata.split()
        name = raw_name.decode('utf-8', errors='replace')
        if private_path(name):
            failures.add((name, 'private file path'))
        if mode == b'160000' or raw_name not in personal_paths:  # Public upstream image submodule, not a regular file.
            continue
        reader.stdin.write(oid + b'\n')
        reader.stdin.flush()
        header = reader.stdout.readline().split()
        data = reader.stdout.read(int(header[2]))
        reader.stdout.read(1)
        # Inspect newly introduced content for credentials. Existing upstream
        # fixtures/history are already public; do not misclassify their dummy keys.
        for rule in content_rules(data):
            try:
                original = git('show', f'{UPSTREAM_BASE}:{name}')
            except subprocess.CalledProcessError:
                original = b''
            if set(RULES[rule].findall(data)) - set(RULES[rule].findall(original)):
                failures.add((name, rule))
    reader.stdin.close()
    reader.wait()
    if args.history:
        commits = git('rev-list', f'{UPSTREAM_BASE}..HEAD').decode().splitlines()
        for commit in commits:
            changed = git('diff-tree', '--root', '-m', '--no-commit-id', '--name-only', '-r', '-z', commit)
            for raw_name in changed.split(b'\0'):
                if raw_name and private_path(raw_name.decode(errors='replace')):
                    failures.add((f'commit {commit[:12]}', 'private file in history'))
            patch = git('show', '--format=', '--no-ext-diff', '--unified=0', commit)
            additions = b'\n'.join(line[1:] for line in patch.splitlines() if line.startswith(b'+') and not line.startswith(b'+++'))
            for rule in content_rules(additions):
                failures.add((f'commit {commit[:12]}', rule))
    if failures:
        for location, rule in sorted(failures):
            print(f'BLOCKED: {location}: {rule}', file=sys.stderr)
        print('Remove private material from the staged files AND unpublished history before pushing. Values are intentionally hidden.', file=sys.stderr)
        return 1
    print('Privacy check passed: tracked paths and personal credentials' + (' including personal history.' if args.history else '.'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
