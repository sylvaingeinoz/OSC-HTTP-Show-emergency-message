import fcntl
import io
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ota
from pi import ota_worker as worker

SHA = 'a' * 40

class OTATests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.base = self.home / '.local/share/stop-show'
        self.app = self.base / 'app'
        self.app.mkdir(parents=True)
        (self.app / 'server.py').write_text('# old')
        (self.app / 'version.json').write_text('{"version":"1.2.0"}')
        (self.base / 'data').mkdir()
        self.settings = self.base / 'data/settings.json'
        self.settings.write_text('{"off_time":0,"hdmi":null}')
        self.before = self.settings.read_bytes()
        service = self.home / '.config/systemd/user/stop-show.service'
        service.parent.mkdir(parents=True)
        service.write_text('unchanged')
        self.manager = ota.Updates(self.app, self.home)
        self.lockfile = self.home / 'install.lock'
        self.patcher = patch('ota.lock_path', return_value=str(self.lockfile))
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_check_pins_commit_and_requires_explicit_install(self):
        candidate = dict(version='1.3.0', revision=SHA)
        with patch('ota.latest', return_value=candidate), patch('ota.subprocess.run') as run:
            result = self.manager.check()
            self.assertEqual(result['available'], candidate)
            run.assert_not_called()
            self.manager.install()
            args = run.call_args.args[0]
            self.assertIn('--unit=stop-show-update', args)
            self.assertEqual(args[-2:], ['--revision', SHA])
            with self.assertRaises(ValueError): self.manager.install()

    def test_same_revision_and_offline_clear_candidate(self):
        (self.app / 'revision.json').write_text(json.dumps({'revision': SHA}))
        with patch('ota.latest', return_value=dict(version='1.2.0', revision=SHA)):
            self.assertIsNone(self.manager.check()['available'])
        self.manager.available = dict(revision=SHA, version='1.3.0')
        with patch('ota.latest', side_effect=OSError('offline')):
            with self.assertRaises(ValueError): self.manager.check()
        self.assertIsNone(self.manager.available)

    def test_installer_lock_rejects_concurrent_install(self):
        self.manager.available = dict(revision=SHA, version='1.3.0')
        with self.lockfile.open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertTrue(self.manager.status()['busy'])
            with self.assertRaises(ValueError): self.manager.install()
        self.assertFalse(self.manager.status()['busy'])

    def test_launch_failure_is_reported(self):
        self.manager.available = dict(revision=SHA, version='1.3.0')
        with patch('ota.subprocess.run', side_effect=OSError('missing')):
            with self.assertRaises(ValueError): self.manager.install()
        self.assertEqual(self.manager.status()['job']['state'], 'error')

    def test_success_keeps_settings_and_backup(self):
        actions = []
        worker.deploy(self.home, ROOT, SHA, ctl=actions.append, health=lambda sha: sha == SHA)
        self.assertEqual(actions, ['stop', 'start'])
        self.assertEqual(self.settings.read_bytes(), self.before)
        self.assertEqual((self.app / 'server.py').read_bytes(), (ROOT / 'server.py').read_bytes())
        self.assertEqual(json.loads((self.base / 'update-status.json').read_text())['state'], 'success')
        self.assertTrue(list(self.base.glob('app-before-*')))

    def test_failed_health_restores_old_code_and_settings(self):
        actions = []
        with self.assertRaises(RuntimeError):
            worker.deploy(self.home, ROOT, SHA, ctl=actions.append, health=lambda sha: False)
        self.assertEqual(actions, ['stop', 'start', 'stop', 'start'])
        self.assertEqual((self.app / 'server.py').read_text(), '# old')
        self.assertEqual(self.settings.read_bytes(), self.before)
        self.assertEqual(json.loads((self.base / 'update-status.json').read_text())['state'], 'error')

    def test_deployed_server_restarts_and_serves_saved_settings(self):
        import socket
        import subprocess
        import time
        import urllib.request
        source = self.home / 'release'
        shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns('__pycache__'))
        (source / 'revision.json').write_text(json.dumps({'revision': SHA}))
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        process = None
        def ctl(action):
            nonlocal process
            if action == 'stop' and process:
                process.terminate(); process.wait(timeout=5); process = None
            if action == 'start':
                process = subprocess.Popen([sys.executable, str(self.app / 'server.py'),
                    '--port', str(port), '--osc-port', '0', '--data', str(self.base / 'data')],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        def health(revision):
            end = time.monotonic() + 5
            while time.monotonic() < end:
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health', timeout=.5) as resp:
                        return json.load(resp)['revision'] == revision
                except OSError: time.sleep(.05)
            return False
        try:
            worker.deploy(self.home, source, SHA, ctl=ctl, health=health)
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/settings') as resp:
                self.assertEqual(json.load(resp)['off_time'], 0)
            self.assertEqual(self.settings.read_bytes(), self.before)
        finally: ctl('stop')

    def test_bad_source_does_not_replace_app(self):
        source = self.home / 'invalid'
        source.mkdir()
        with self.assertRaises(ValueError):
            worker.deploy(self.home, source, SHA, ctl=lambda action: None)
        self.assertEqual((self.app / 'server.py').read_text(), '# old')

    def archive(self, malicious=None):
        out = io.BytesIO()
        with tarfile.open(fileobj=out, mode='w:gz') as tar:
            if malicious:
                m = tarfile.TarInfo(malicious)
                m.size = 1
                tar.addfile(m, io.BytesIO(b'x'))
            else:
                for p in ROOT.rglob('*'):
                    if p.is_file() and '__pycache__' not in p.parts:
                        tar.add(p, arcname='repo/' + str(p.relative_to(ROOT)))
        return out.getvalue()

    def test_archive_download_fixed_url_and_revision(self):
        blob = self.archive()
        with patch('pi.ota_worker.urlopen', return_value=io.BytesIO(blob)) as opened:
            source = worker.download(SHA, self.home)
        self.assertEqual(opened.call_args.args[0].full_url, f'https://codeload.github.com/{ota.REPO}/tar.gz/{SHA}')
        self.assertEqual(json.loads((source / 'revision.json').read_text())['revision'], SHA)
        worker.deploy(self.home, source, SHA, ctl=lambda action: None, health=lambda sha: True)
        self.assertEqual(json.loads((self.app / 'revision.json').read_text())['revision'], SHA)
        self.assertEqual(self.settings.read_bytes(), self.before)

    def test_archive_escape_and_arbitrary_revision_rejected(self):
        with self.assertRaises(ValueError): worker.download('https://evil.test', self.home)
        with patch('pi.ota_worker.urlopen', return_value=io.BytesIO(self.archive('repo/../../escape'))):
            with self.assertRaises(ValueError): worker.download(SHA, self.home)
        self.assertFalse((self.home.parent / 'escape').exists())

    def test_latest_reads_version_at_exact_commit(self):
        with patch('ota.get_json', side_effect=[{'sha':SHA}, {'version':'1.3.0'}]) as get:
            self.assertEqual(ota.latest()['revision'], SHA)
            self.assertIn('/' + SHA + '/version.json', get.call_args.args[0])

if __name__ == '__main__': unittest.main()
