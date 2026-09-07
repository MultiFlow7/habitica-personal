"""Cloud-only end-to-end CLI checks. Never target the production database."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
from urllib import request

ROOT = Path(__file__).resolve().parents[1]
URL = 'http://127.0.0.1:8317'


def main():
    if os.environ.get('GITHUB_ACTIONS') != 'true' or not os.environ.get('RUNNER_TEMP'):
        raise SystemExit('Refusing live tests outside the isolated GitHub Actions job.')
    username = 'cli_' + secrets.token_hex(8)
    password = secrets.token_urlsafe(24)
    user_id = None
    api_token = None
    env = {k: v for k, v in os.environ.items() if not k.startswith('HABITICA_')}
    with tempfile.TemporaryDirectory(prefix='habitica-cli-', dir=os.environ['RUNNER_TEMP']) as temp:
        config = str(Path(temp) / 'config.json')
        def run(*args, stdin=None, expected=0):
            result = subprocess.run([sys.executable, str(ROOT / 'habitica'), '--config', config,
                                     '--url', URL, *args], input=stdin, text=True, capture_output=True, env=env, timeout=45)
            assert result.returncode == expected, f'CLI {args[:2]} failed with exit {result.returncode}; details withheld'
            assert password not in result.stdout and password not in result.stderr
            if api_token:
                assert api_token not in result.stdout and api_token not in result.stderr
            value = json.loads(result.stdout)
            assert value['ok'] == (expected == 0)
            return value.get('data', value.get('error'))
        try:
            run('status')
            body = json.dumps({'username': username, 'email': username + '@example.com',
                               'password': password, 'confirmPassword': password}).encode()
            req = request.Request(URL + '/api/v3/user/auth/local/register', data=body,
                                  headers={'Content-Type': 'application/json', 'x-client': 'habitica-cli-ci'})
            with request.urlopen(req, timeout=30) as response:
                registered = json.load(response)['data']
                user_id, api_token = registered['_id'], registered['apiToken']
            run('auth', 'login', '--username', username, '--password-stdin', stdin=password)
            assert run('auth', 'status')['configured']
            user = run('user', 'get')
            assert user['_id'] == user_id and user.get('apiToken') in (None, '[REDACTED]')
            tag = run('tags', 'create', '--name', 'CLI tag')
            tag_id = tag.get('id') or tag['_id']
            run('tags', 'update', tag_id, '--name', 'CLI renamed')
            assert any(t['name'] == 'CLI renamed' for t in run('tags', 'list'))
            created = {}
            for kind in ['todo', 'habit', 'daily', 'reward']:
                task = run('tasks', 'create', '--data', '-', stdin=json.dumps({'type': kind, 'text': 'CLI ' + kind, **({'value': 0} if kind == 'reward' else {})}))
                created[kind] = task.get('_id') or task['id']
                assert any((t.get('_id') or t.get('id')) == created[kind] for t in run('tasks', 'list', '--type', kind))
            todo = created['todo']
            run('tasks', 'update', todo, '--notes', '私密测试说明')
            run('tasks', 'tag-add', todo, tag_id)
            assert len(run('tasks', 'list', '--type', 'todo', '--search', '私密测试', '--tag', tag_id)) == 1
            run('checklist', 'add', todo, '--text', '检查项')
            item = run('tasks', 'get', todo)['checklist'][0]
            item_id = item.get('id') or item['_id']
            run('checklist', 'update', todo, item_id, '--text', '更新检查项')
            assert run('checklist', 'complete', todo, item_id)['changed']
            assert not run('checklist', 'complete', todo, item_id)['changed']
            assert run('checklist', 'undo', todo, item_id)['changed']
            run('checklist', 'delete', todo, item_id, '--yes')
            before = run('user', 'get')['stats']
            assert run('tasks', 'complete', todo)['changed']
            assert not run('tasks', 'complete', todo)['changed']
            after = run('user', 'get')['stats']
            assert after['exp'] > before['exp'] and after['gp'] > before['gp']
            assert any(t['_id'] == todo for t in run('tasks', 'list', '--type', 'completedTodos'))
            assert run('tasks', 'undo', todo)['changed']
            assert run('tasks', 'complete', created['daily'])['changed']
            run('tasks', 'score', created['habit'], 'up')
            run('tasks', 'score', created['habit'], 'down')
            run('tasks', 'score', created['reward'], 'up')
            run('tasks', 'tag-remove', todo, tag_id)
            run('tags', 'delete', tag_id, '--yes')
            for task_id in created.values():
                run('tasks', 'delete', task_id, '--yes')
            run('tasks', 'get', todo, expected=4)
            run('auth', 'logout')
            assert not Path(config).exists()
            run('user', 'get', expected=3)
            print('PASS: CLI login, four task types, CRUD, filtering, scoring, repeat-safe completion, undo, tags, checklists, redaction and logout')
        finally:
            # Exact randomly generated fixture only; no broad deletion or production tests.
            cleanup = '''
import mongoose from 'mongoose';
import {readFileSync} from 'node:fs';
const config = JSON.parse(readFileSync('config.json', 'utf8'));
await mongoose.connect(config.NODE_DB_URI);
const users = mongoose.connection.collection('users');
const user = await users.findOne({'auth.local.username': FIXTURE_USERNAME});
if (user && (!FIXTURE_ID || user._id === FIXTURE_ID)) {
  for (const name of ['tasks', 'registrationevents', 'userhistories']) {
    await mongoose.connection.collection(name).deleteMany({userId: user._id});
  }
  await users.deleteOne({_id: user._id, 'auth.local.username': FIXTURE_USERNAME});
}
await mongoose.disconnect();
'''
            source = 'const FIXTURE_USERNAME=' + json.dumps(username) + ';const FIXTURE_ID=' + json.dumps(user_id) + ';\n' + cleanup
            result = subprocess.run(['docker', 'compose', '-f', 'deploy/compose.yml', 'exec', '-T', 'app',
                                     'node', '--input-type=module'], input=source, text=True, cwd=ROOT,
                                    capture_output=True, timeout=45)
            if result.returncode:
                raise RuntimeError('CLI fixture cleanup failed; CI will remove its isolated volume.')


if __name__ == '__main__':
    main()
