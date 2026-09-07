#!/usr/bin/env python3
import importlib.util
import pathlib
import unittest

spec = importlib.util.spec_from_file_location('privacy_check', pathlib.Path(__file__).with_name('privacy-check.py'))
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class PrivacyTests(unittest.TestCase):
    def test_private_paths(self):
        for name in ['config.json', 'deploy/.env', '.env.production', 'nested/backups/export.gz', 'data/users.bson', 'dump.archive.gz', '.habitica-server.json', 'work/runtime/bin/node', 'id_ed25519']:
            with self.subTest(name=name):
                self.assertTrue(guard.private_path(name))

    def test_source_paths(self):
        for name in ['config.json.example', '.env.example', 'deploy/configure.py', 'website/server/models/user/schema.js', 'package-lock.json']:
            with self.subTest(name=name):
                self.assertFalse(guard.private_path(name))

    def test_secret_patterns(self):
        samples = [b'ghp_' + b'A' * 36, b'-----BEGIN ' + b'OPENSSH PRIVATE KEY-----', b'mongodb://' + b'alice:password@localhost/db']
        for sample in samples:
            self.assertTrue(guard.content_rules(sample))

    def test_placeholders(self):
        self.assertFalse(guard.content_rules(b'mongodb://mongo:27017/habitica?replicaSet=rs'))
        self.assertFalse(guard.content_rules(b'process.env.GITHUB_TOKEN'))


if __name__ == '__main__':
    unittest.main()
