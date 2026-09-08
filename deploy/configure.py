#!/usr/bin/env python3
"""Generate a private runtime configuration from the upstream example."""
import argparse
import json
from pathlib import Path
import secrets

parser = argparse.ArgumentParser()
parser.add_argument('--template', default='config.json.example')
parser.add_argument('--output', default='config.json')
parser.add_argument('--url', default='http://127.0.0.1:8317')
args = parser.parse_args()
target = Path(args.output)
if target.exists():
    raise SystemExit('Configuration already exists; refusing to replace secrets.')
config = json.loads(Path(args.template).read_text())
config.update({
    'NODE_ENV': 'production', 'HOST': '0.0.0.0', 'PORT': 3000,
    'BASE_URL': args.url, 'WEB_CONCURRENCY': 0,
    'NODE_DB_URI': 'mongodb://mongo:27017/habitica?replicaSet=rs&directConnection=true',
    'MONGODB_POOL_SIZE': '5', 'MONGODB_MIN_POOL_SIZE': '1',
    'SESSION_SECRET': secrets.token_hex(32), 'SESSION_SECRET_KEY': secrets.token_hex(32),
    'ENABLE_CONSOLE_LOGS_IN_PROD': 'true', 'DISABLE_EMAILS': 'true',
    'DISABLE_LOCAL_ANALYTICS': True,
    'LOGGLY_TOKEN': '', 'LOGGLY_SUBDOMAIN': '', 'LOGGLY_CLIENT_TOKEN': '',
    'SLACK_URL': '', 'SLACK_FLAGGING_URL': '', 'SLACK_SUBSCRIPTIONS_URL': '',
    'GOOGLE_CLIENT_ID': '', 'GOOGLE_CLIENT_SECRET': '', 'FACEBOOK_KEY': '',
    'FACEBOOK_SECRET': '', 'AMPLITUDE_KEY': '', 'AMPLITUDE_SECRET': '', 'GA_ID': '',
    'TRUSTED_DOMAINS': 'http://localhost,http://127.0.0.1,' + args.url,
})
with target.open('x') as output:
    json.dump(config, output, indent=2)
    output.write('\n')
target.chmod(0o600)
print('Private runtime configuration created.')
