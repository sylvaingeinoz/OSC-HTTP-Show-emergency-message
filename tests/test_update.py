import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('update_app', SOURCE / 'pi/update_app.py')
update_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update_app)

class UpdateTests(unittest.TestCase):
    def test_update_preserves_settings_autostart_and_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            base = home / '.local/share/stop-show'
            (base / 'app').mkdir(parents=True)
            (base / 'app/server.py').write_text('# ancienne version')
            (base / 'data').mkdir()
            config = base / 'data/settings.json'
            config.write_text('{"off_time":0,"indicator":true,"hdmi":{"transform":"180"}}')
            service = home / '.config/systemd/user/stop-show.service'
            service.parent.mkdir(parents=True)
            service.write_text('service existant')
            before = config.read_bytes()
            backup = update_app.update(home)
            self.assertEqual(config.read_bytes(), before)
            self.assertEqual(service.read_text(), 'service existant')
            self.assertEqual((backup / 'server.py').read_text(), '# ancienne version')
            self.assertEqual((base / 'app/server.py').read_bytes(), (SOURCE / 'server.py').read_bytes())
            second = update_app.update(home)
            self.assertNotEqual(backup, second)
            self.assertEqual(config.read_bytes(), before)
    def test_failed_swap_restores_previous_app(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            app = home / '.local/share/stop-show/app'
            app.mkdir(parents=True)
            (app / 'server.py').write_text('ancienne version')
            rename = Path.rename
            def fail_stage(path, target):
                if path.name.startswith('.update-'): raise OSError('échec simulé')
                return rename(path, target)
            with patch.object(Path, 'rename', fail_stage):
                with self.assertRaises(OSError): update_app.update(home)
            self.assertEqual((app / 'server.py').read_text(), 'ancienne version')
    def test_missing_install_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError): update_app.update(Path(directory))
