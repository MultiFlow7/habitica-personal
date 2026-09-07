"""Transport and command tests against a disposable local HTTP server."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('habitica_cli', Path(__file__).with_name('main.py'))
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)
USER = 'a' * 8 + ('-' + 'a' * 4) * 3 + '-' + 'a' * 12
TOKEN = 'b' * 8 + ('-' + 'b' * 4) * 3 + '-' + 'b' * 12


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def handle_request(self):
        body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        record = (self.command, self.path, {k.lower(): v for k, v in self.headers.items()}, json.loads(body) if body else None)
        self.server.records.append(record)
        status, payload, headers = self.server.respond(record)
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    do_GET = do_POST = do_PUT = do_DELETE = handle_request


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = Path(self.temp.name) / 'config.json'
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.records = []
        self.server.respond = lambda r: (200, {'success': True, 'data': {}}, {})
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        self.environment = patch.dict(os.environ, {k: v for k, v in os.environ.items() if not k.startswith('HABITICA_')}, clear=True)
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def configured(self):
        cli.save_config(self.config, {'url': self.url, 'user_id': USER, 'api_token': TOKEN})

    def invoke(self, *args, stdin=''):
        output = io.StringIO()
        with patch('sys.stdin', io.StringIO(stdin)), contextlib.redirect_stdout(output):
            code = cli.main(['--config', str(self.config), '--url', self.url, *args])
        raw = output.getvalue()
        self.assertNotIn(TOKEN, raw)
        return code, json.loads(raw)

    def test_login_saves_private_credentials_without_password(self):
        self.server.respond = lambda r: (200, {'success': True, 'data': {'id': USER, 'apiToken': TOKEN}}, {})
        code, result = self.invoke('auth', 'login', '--username', 'agent', '--password-stdin', stdin='test password\n')
        self.assertEqual(code, 0)
        self.assertTrue(result['data']['authenticated'])
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode), 0o600)
        self.assertNotIn('test password', self.config.read_text())
        self.assertEqual(json.loads(self.config.read_text())['api_token'], TOKEN)
        self.assertNotIn('x-api-key', self.server.records[0][2])

    def test_set_validates_credentials_before_saving(self):
        code, _ = self.invoke('auth', 'set', '--user-id', USER, '--token-stdin', stdin=TOKEN)
        self.assertEqual(code, 0)
        self.assertEqual(self.server.records[0][2]['x-api-key'], TOKEN)
        self.assertTrue(self.config.exists())

    def test_auth_failure_does_not_overwrite_credentials(self):
        self.configured()
        original = self.config.read_bytes()
        self.server.respond = lambda r: (401, {'password': TOKEN}, {})
        code, _ = self.invoke('auth', 'login', '--username', 'bad', '--password-stdin', stdin='wrong')
        self.assertEqual(code, 3)
        self.assertEqual(self.config.read_bytes(), original)

    def test_permissions_and_symlinks_rejected(self):
        self.configured()
        self.config.chmod(0o644)
        self.assertEqual(self.invoke('user', 'get')[0], 3)
        self.config.chmod(0o600)
        target = self.config.with_name('other.json')
        self.config.rename(target)
        self.config.symlink_to(target)
        self.assertEqual(self.invoke('user', 'get')[0], 3)

    def test_origin_mismatch_never_sends_request(self):
        self.configured()
        code, _ = self.invoke('--url', 'https://example.com', 'user', 'get')
        self.assertEqual(code, 3)
        self.assertEqual(len(self.server.records), 0)

    def test_redirect_does_not_forward_credentials(self):
        self.configured()
        self.server.respond = lambda r: (302, {}, {'Location': self.url + '/elsewhere'})
        code, result = self.invoke('user', 'get')
        self.assertEqual(code, 6)
        self.assertEqual(result['error']['http_status'], 302)
        self.assertEqual(len(self.server.records), 1)

    def test_status_has_no_auth_headers(self):
        self.configured()
        self.assertEqual(self.invoke('status')[0], 0)
        self.assertNotIn('x-api-key', self.server.records[0][2])

    def test_missing_and_partial_env_credentials(self):
        self.assertEqual(self.invoke('user', 'get')[0], 3)
        with patch.dict(os.environ, {'HABITICA_USER_ID': USER}):
            self.assertEqual(self.invoke('user', 'get')[0], 3)
        with patch.dict(os.environ, {'HABITICA_USER_ID': USER, 'HABITICA_API_TOKEN': TOKEN}):
            self.assertEqual(self.invoke('user', 'get')[0], 3)
        self.assertFalse(self.server.records)

    def test_output_redacts_nested_credentials(self):
        self.configured()
        data = {'stats': {'gp': 12}, 'apiToken': TOKEN, 'auth': {'local': {'hashed_password': 'hash'}}, 'notes': TOKEN}
        self.server.respond = lambda r: (200, {'success': True, 'data': data}, {})
        code, result = self.invoke('user', 'get')
        self.assertEqual(code, 0)
        self.assertEqual(result['data']['auth']['local']['hashed_password'], '[REDACTED]')
        self.assertEqual(result['data']['stats']['gp'], 12)

    def test_task_type_mapping_and_local_filter(self):
        self.configured()
        data = [{'text': '写作', 'notes': '书稿', 'tags': ['tag1']}, {'text': 'Read', 'tags': []}]
        self.server.respond = lambda r: (200, {'success': True, 'data': data}, {})
        _, result = self.invoke('tasks', 'list', '--type', 'todo', '--search', '书稿', '--tag', 'tag1')
        self.assertEqual(len(result['data']), 1)
        self.assertEqual(self.server.records[0][1], '/api/v3/tasks/user?history=false&type=todos')

    def test_create_json_and_explicit_fields(self):
        self.configured()
        self.assertEqual(self.invoke('tasks', 'create', '--type', 'daily', '--text', '喝水', '--data', '-', stdin='{"notes":"test","everyX":2}')[0], 0)
        self.assertEqual(self.server.records[0][3], {'notes': 'test', 'everyX': 2, 'type': 'daily', 'text': '喝水'})

    def test_complete_twice_only_scores_once_and_undo(self):
        self.configured()
        task = {'id': 'task1', 'type': 'todo', 'completed': False}
        def respond(record):
            if record[0] == 'POST':
                task['completed'] = record[1].endswith('/up')
            return 200, {'success': True, 'data': dict(task)}, {}
        self.server.respond = respond
        self.assertTrue(self.invoke('tasks', 'complete', 'task1')[1]['data']['changed'])
        self.assertFalse(self.invoke('tasks', 'complete', 'task1')[1]['data']['changed'])
        self.assertEqual(sum(r[0] == 'POST' for r in self.server.records), 1)
        self.assertTrue(self.invoke('tasks', 'undo', 'task1')[1]['data']['changed'])

    def test_checklist_completion_already_done_is_noop(self):
        self.configured()
        self.server.respond = lambda r: (200, {'success': True, 'data': {'checklist': [{'id': 'i1', 'completed': True}]}}, {})
        self.assertFalse(self.invoke('checklist', 'complete', 't1', 'i1')[1]['data']['changed'])
        self.assertEqual(len(self.server.records), 1)

    def test_delete_requires_yes(self):
        self.configured()
        self.assertEqual(self.invoke('tasks', 'delete', 'task1')[0], 2)
        self.assertFalse(self.server.records)
        self.assertEqual(self.invoke('tasks', 'delete', 'task1', '--yes')[0], 0)
        self.assertEqual(self.server.records[0][0], 'DELETE')

    def test_input_validation_before_network(self):
        self.configured()
        for args in [('tasks', 'get', '../user'), ('tasks', 'create', '--data', '[]'),
                     ('tasks', 'create', '--text', 'missing type'), ('tasks', 'update', 't', '--data', '{"completed":true}'),
                     ('tasks', 'update', 't', '--type', 'daily'), ('tasks', 'update', 't', '--data', '{"type":"daily"}'),
                     ('tasks', 'create', '--type', 'reward', '--text', 'x', '--value', 'nan')]:
            self.assertEqual(self.invoke(*args)[0], 2)
        self.assertFalse(self.server.records)

    def test_http_errors_are_structured_and_not_retried(self):
        self.configured()
        for http_status, exit_code in [(401, 3), (404, 4), (409, 7), (429, 6), (500, 6)]:
            self.server.records.clear()
            self.server.respond = lambda r: (http_status, {'message': TOKEN}, {'Retry-After': '9'})
            code, result = self.invoke('tasks', 'score', 't1', 'up')
            self.assertEqual(code, exit_code)
            self.assertEqual(result['error']['http_status'], http_status)
            self.assertEqual(len(self.server.records), 1)

    def test_network_write_reports_unknown_outcome(self):
        self.configured()
        with patch.object(cli.request.OpenerDirector, 'open', side_effect=TimeoutError):
            code, result = self.invoke('tasks', 'score', 'task1', 'up')
        self.assertEqual(code, 5)
        self.assertTrue(result['error']['outcome_unknown'])

    def test_complete_rejects_habits_without_scoring(self):
        self.configured()
        self.server.respond = lambda r: (200, {'success': True, 'data': {'type': 'habit'}}, {})
        self.assertEqual(self.invoke('tasks', 'complete', 't1')[0], 2)
        self.assertEqual([r[0] for r in self.server.records], ['GET'])

    def test_malformed_success_response_does_not_escape_json_contract(self):
        self.configured()
        self.server.respond = lambda r: (200, {'success': True, 'data': float('nan')}, {})
        code, result = self.invoke('user', 'get')
        self.assertEqual(code, 6)
        self.assertEqual(result['error']['code'], 'api')

    def test_disallow_insecure_remote_url_and_embedded_credentials(self):
        for url in ['http://example.com', 'https://user:secret@example.com', 'https://example.com/path', 'https://example.com?key=secret']:
            with self.assertRaises(cli.Failure):
                cli.safe_url(url)

    def test_machine_schema_and_real_entrypoint(self):
        result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'habitica'), 'schema'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        commands = [x['command'] for x in json.loads(result.stdout)['data']['commands']]
        self.assertIn('tasks complete', commands)
        self.assertIn('checklist undo', commands)


if __name__ == '__main__':
    unittest.main()
