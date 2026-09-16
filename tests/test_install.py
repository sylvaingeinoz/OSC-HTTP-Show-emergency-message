"""Essais du configurateur système sur une racine factice ; aucun sudo."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
import xml.etree.ElementTree as ET

PI = Path(__file__).resolve().parents[1] / 'pi'
spec = importlib.util.spec_from_file_location('configure_pi', PI / 'configure_pi.py')
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'boot/firmware').mkdir(parents=True)
        (self.root / 'etc/lightdm').mkdir(parents=True)
        self.originals = {
            'boot/firmware/cmdline.txt': 'console=serial0,115200 console=tty1 root=PARTUUID=abcd rootfstype=ext4 fsck.repair=yes rootwait quiet splash\n',
            'boot/firmware/config.txt': '[all]\ndtoverlay=vc4-kms-v3d\n[pi5]\narm_boost=1\n',
            'etc/lightdm/lightdm.conf': '[LightDM]\nminimum-vt=7\n[Seat:*]\nuser-session=LXDE-pi-labwc\nautologin-user=regie\n[Seat:seat0]\nautologin-session=old\n',
        }
        for name, text in self.originals.items(): (self.root / name).write_text(text)
    def tearDown(self): self.tmp.cleanup()
    def test_repeated_install_is_identical_and_keeps_original_backup(self):
        config.Installer(self.root).apply('regie')
        first = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        config.Installer(self.root).apply('regie')
        second = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(first, second)
        for name, text in self.originals.items():
            self.assertEqual((self.root / 'var/lib/stop-show-install/files' / name).read_text(), text)
    def test_restore_exactly_recovers_files_and_removes_added_session(self):
        installer = config.Installer(self.root)
        installer.apply('regie')
        config.Installer(self.root).restore()
        for name, text in self.originals.items(): self.assertEqual((self.root / name).read_text(), text)
        self.assertFalse((self.root / 'usr/share/wayland-sessions/stop-show.desktop').exists())
        self.assertFalse((self.root / 'etc/systemd/system/getty@tty1.service.d/stop-show.conf').exists())
        config.Installer(self.root).restore()  # Restauration répétable.
    def test_boot_keeps_root_serial_and_single_line(self):
        result = config.quiet_cmdline(self.originals['boot/firmware/cmdline.txt'])
        self.assertIn('root=PARTUUID=abcd', result)
        self.assertIn('console=serial0,115200', result)
        self.assertIn('console=tty3', result)
        self.assertNotIn('console=tty1', result)
        self.assertNotIn('splash', result.split())
        self.assertEqual(len(result.splitlines()), 1)
        self.assertEqual(config.quiet_cmdline(result), result)
        with self.assertRaises(ValueError): config.quiet_cmdline('root=x\nroot=y\n')
    def test_invalid_boot_aborts_before_any_write(self):
        p = self.root / 'boot/firmware/cmdline.txt'
        p.write_text('broken\nsecond line\n')
        with self.assertRaises(ValueError): config.Installer(self.root).apply('regie')
        self.assertFalse((self.root / 'var/lib/stop-show-install/manifest.json').exists())
    def test_lightdm_selects_dedicated_session_on_specific_seat_too(self):
        result = config.lightdm_config(self.originals['etc/lightdm/lightdm.conf'], 'regie')
        self.assertEqual(result.count('autologin-session=stop-show'), 2)
        self.assertNotIn('autologin-session=old', result)
        self.assertIn('minimum-vt=7', result)
        self.assertEqual(config.lightdm_config(result, 'regie'), result)
    def test_cursor_has_transparent_pixel_and_valid_header(self):
        data = config.transparent_cursor()
        self.assertEqual(data[:4], b'Xcur')
        self.assertEqual(len(data), 68)
        self.assertEqual(struct.unpack_from('<3I', data, 16), (0xfffd0002, 24, 28))
        self.assertEqual(struct.unpack_from('<9I', data, 28), (36, 0xfffd0002, 24, 1, 1, 1, 0, 0, 0))
        self.assertEqual(data[-4:], b'\0' * 4)
    def test_session_config_well_formed_and_no_desktop_autostart(self):
        tree = ET.parse(PI / 'labwc/rc.xml')
        self.assertEqual(tree.getroot().tag, 'labwc_config')
        text = (PI / 'labwc/autostart').read_text()
        for process in ['lxpanel', 'pcmanfm', 'wf-panel-pi', 'swayidle']:
            self.assertNotIn(process, text)
        self.assertIn('swaybg', text)
    def test_unsafe_username_rejected(self):
        with self.assertRaises(ValueError): config.Installer(self.root).apply('regie\nautologin-user=root')
        self.assertFalse((self.root / 'var/lib/stop-show-install/manifest.json').exists())


if __name__ == '__main__': unittest.main()
