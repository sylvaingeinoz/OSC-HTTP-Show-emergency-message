import copy
import json
import math
from pathlib import Path
import socket
import struct
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import App, DisplayHardware, Handler, OSCHandler, ThreadingHTTPServer, UDPServer, decode_osc, osc_command


def osc(address, *args):
    def s(value):
        data = value.encode() + b'\0'
        return data + b'\0' * (-len(data) % 4)
    tags, body = ',', b''
    for arg in args:
        if isinstance(arg, str): tags += 's'; body += s(arg)
        elif isinstance(arg, int): tags += 'i'; body += struct.pack('>i', arg)
        else: tags += 'f'; body += struct.pack('>f', arg)
    return s(address) + s(tags) + body


class Hardware:
    def __init__(self):
        self.current = dict(output='HDMI-A-1', mode='1920x1080@60.000000Hz', transform='normal')
        self.calls = []
    def validate(self, data): return copy.deepcopy(self.current)
    def apply(self, data): self.current = copy.deepcopy(data); self.calls.append(copy.deepcopy(data))


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.now = 100
        self.wall = 1798757990  # Valeur fixe, aucune dépendance à la date du test.
        self.hw = Hardware()
        self.app = App(self.tmp.name, hardware=self.hw, mono=lambda: self.now, wall=lambda: self.wall)
    def tearDown(self): self.tmp.cleanup()
    def test_boot_black_without_token(self):
        self.assertEqual(self.app.snapshot()['cue']['mode'], 'black')
        self.assertFalse((Path(self.tmp.name) / 'token').exists())
    def test_every_mode_expires_including_stop(self):
        for data in [dict(mode='text', text='Micro 2'), dict(mode='stop'), dict(mode='clock'), dict(mode='timer', seconds=60), dict(mode='countdown', target='2099-01-01T00:00:00+01:00'), dict(mode='test')]:
            self.app.command(data)
            self.now += 14.9
            self.assertEqual(self.app.snapshot()['cue']['mode'], data['mode'])
            self.now += .1
            self.assertEqual(self.app.snapshot()['cue']['mode'], 'black')
    def test_zero_disables_timeout_for_all_cues(self):
        self.app.configure({'off_time': 0})
        for data in [dict(mode='stop'), dict(mode='text', text='REPRISE'), dict(mode='clock'), dict(mode='test'), dict(mode='timer', seconds=2), dict(mode='countdown', target='2099-01-01T00:00:00Z')]:
            self.app.command(data)
            self.now += 100000
            state = self.app.snapshot()
            self.assertEqual(state['cue']['mode'], data['mode'])
            self.assertIsNone(state['remaining'])
            self.app.command({'mode': 'keepalive'})
            self.assertIsNone(self.app.snapshot()['remaining'])
        self.app.command({'mode': 'black'})
        self.assertEqual(self.app.snapshot()['cue']['mode'], 'black')
    def test_zero_toggle_affects_live_cue_without_reviving_expired(self):
        self.app.command({'mode': 'stop'})
        self.now += 10
        self.app.configure({'off_time': 0})
        self.now += 1000
        self.assertEqual(self.app.snapshot()['cue']['mode'], 'stop')
        self.app.configure({'off_time': 5})
        self.assertEqual(self.app.snapshot()['remaining'], 5)
        self.now += 5
        self.app.configure({'off_time': 0})
        self.assertEqual(self.app.snapshot()['cue']['mode'], 'black')
    def test_old_token_file_is_ignored_and_settings_preserved(self):
        (Path(self.tmp.name) / 'token').write_text('ancienne-cle')
        self.app.configure({'off_time': 0, 'indicator': True})
        app = App(self.tmp.name)
        self.assertEqual(app.config['off_time'], 0)
        self.assertTrue(app.config['indicator'])
        self.assertEqual(app.command({'mode': 'stop'})['cue']['mode'], 'stop')

    def test_identical_information_rearms(self):
        data = dict(mode='stop')
        self.app.command(data)
        self.now += 14
        self.app.command(data)
        self.now += 2
        self.assertEqual(self.app.snapshot()['cue']['mode'], 'stop')
        self.assertEqual(self.app.snapshot()['remaining'], 13)
    def test_poll_and_settings_do_not_rearm(self):
        self.app.command(dict(mode='stop'))
        self.now += 14
        self.app.configure(dict(off_time=30))
        self.app.snapshot()
        self.now += 1
        self.assertEqual(self.app.snapshot()['cue']['mode'], 'black')
    def test_keepalive_does_not_restart_timer_or_resurrect_expired(self):
        self.app.command(dict(mode='timer', seconds=100))
        self.now += 10
        self.app.command(dict(mode='keepalive'))
        self.assertEqual(self.app.snapshot()['cue']['remaining'], 90)
        self.assertEqual(self.app.snapshot()['remaining'], 15)
        self.now += 16
        self.app.command(dict(mode='keepalive'))
        self.assertEqual(self.app.snapshot()['cue']['mode'], 'black')
    def test_black_immediate_and_replacement(self):
        self.app.command(dict(mode='stop'))
        self.app.command(dict(mode='text', text='REPRISE'))
        self.assertEqual(self.app.snapshot()['cue']['text'], 'REPRISE')
        self.app.command(dict(mode='black'))
        self.assertEqual(self.app.snapshot()['remaining'], 0)
    def test_monotonic_timer_ignores_wall_clock_adjustment(self):
        self.app.command(dict(mode='timer', seconds=300))
        self.wall += 10000
        self.now += 2
        self.assertEqual(self.app.snapshot()['cue']['remaining'], 298)
    def test_target_requires_offset_and_stops_at_zero(self):
        for target in ['2027-01-01T00:00:00', '2000-01-01T00:00:00Z', 'minuit', None]:
            with self.assertRaises(ValueError): self.app.command(dict(mode='countdown', target=target))
        self.app.command(dict(mode='countdown', target='2099-01-01T00:00:00+01:00'))
        target = self.app.snapshot()['cue']['target']
        self.wall = target - 2
        self.assertEqual(self.app.snapshot()['cue']['remaining'], 2)
        self.wall = target + 2
        self.assertEqual(self.app.snapshot()['cue']['remaining'], 0)
    def test_invalid_commands_are_atomic(self):
        self.app.command(dict(mode='stop'))
        for cmd in [{}, [], dict(mode='text', text=''), dict(mode='timer', seconds=True), dict(mode='timer', seconds=float('nan')), dict(mode='timer', seconds=-1), dict(mode='stop', extra=1)]:
            with self.assertRaises(ValueError): self.app.command(cmd)
            self.assertEqual(self.app.snapshot()['cue']['mode'], 'stop')
    def test_config_validation_and_persistence(self):
        self.app.configure(dict(off_time=23, indicator=True, font='mono', timezone='UTC'))
        app2 = App(self.tmp.name)
        self.assertEqual(app2.config['off_time'], 23)
        for value in [dict(off_time=-1), dict(off_time=float('inf')), dict(indicator='false'), dict(size=900), dict(timezone='../UTC'), dict(font='custom'), dict(hdmi={})]:
            with self.assertRaises(ValueError): self.app.configure(value)
        self.assertEqual(self.app.config['off_time'], 23)
    def test_failed_write_does_not_change_config(self):
        with patch('server.save_json', side_effect=OSError('disque plein')):
            with self.assertRaises(OSError): self.app.configure(dict(off_time=60))
        self.assertEqual(self.app.config['off_time'], 15)
    def test_hdmi_timeout_and_confirmation(self):
        old = copy.deepcopy(self.hw.current)
        new = {**old, 'transform': '90'}
        self.app.hdmi_test(new)
        with self.assertRaises(ValueError): self.app.hdmi_test(new)
        self.now += 20
        self.app.tick()
        self.assertEqual(self.hw.current, old)
        with self.assertRaises(ValueError): self.app.hdmi_confirm()
        self.app.hdmi_test(new)
        self.app.hdmi_confirm()
        self.now += 30
        self.app.tick()
        self.assertEqual(self.hw.current, new)
        self.assertEqual(App(self.tmp.name).config['hdmi'], new)
    def test_late_confirmation_cannot_persist(self):
        self.app.hdmi_test({**self.hw.current, 'transform': '180'})
        self.now += 21
        with self.assertRaises(ValueError): self.app.hdmi_confirm()
        self.assertIsNone(self.app.config['hdmi'])
    def test_osc_commands_without_token(self):
        for address, args, mode in [('/show/text', ('Léa → micro 2',), 'text'), ('/show/stop', (), 'stop'), ('/show/timer', (30.5,), 'timer'), ('/show/countdown', ('2099-01-01T00:00:00+01:00',), 'countdown'), ('/show/clock', (), 'clock'), ('/show/test', (), 'test'), ('/show/black', (), 'black')]:
            self.assertEqual(osc_command(self.app, osc(address, *args))['cue']['mode'], mode)
        for packet in [osc('/show/text'), osc('/show/stop', 'STOP', 'extra'), osc('/show/unknown')]:
            with self.assertRaises(ValueError): osc_command(self.app, packet)
    def test_osc_malformed(self):
        good = osc('/show/text', 'Bonjour')
        for packet in [b'', b'#bundle\0' + b'\0' * 8, good[:-1], good + b'\0' * 4, b'/show/stop\0\0,f\0\0', osc('/elsewhere', 'test')]:
            with self.assertRaises((ValueError, UnicodeError)): decode_osc(packet)
    def test_output_parser_and_mode_allowlist(self):
        hardware = DisplayHardware()
        listing = 'HDMI-A-1 "TV"\n  Enabled: yes\n  Modes:\n    1920x1080 px, 60.000000 Hz (preferred, current)\n    1920x1080 px, 59.940000 Hz\n  Transform: normal\nDP-1 "Other"\n  Enabled: yes\n'
        with patch.object(hardware, 'run', return_value=listing):
            outputs = hardware.outputs()
            self.assertEqual(len(outputs), 1)
            self.assertEqual(len(outputs[0]['modes']), 2)
            hardware.validate(dict(output='HDMI-A-1', mode='1920x1080@59.940000Hz', transform='flipped-180'))
            for mode in ['9999x9999@60Hz', '1920x1080@60Hz; touch /tmp/bad']:
                with self.assertRaises(ValueError): hardware.validate(dict(output='HDMI-A-1', mode=mode, transform='normal'))
    def test_hardware_no_shell(self):
        with patch('server.subprocess.run') as run:
            run.return_value.returncode = 0
            DisplayHardware().apply(self.hw.current)
            self.assertEqual(run.call_args.args[0][0], 'wlr-randr')
            self.assertNotIn('shell', run.call_args.kwargs)


class NetworkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.app = App(cls.tmp.name)
        cls.http = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.http.app = cls.app
        cls.udp = UDPServer(('127.0.0.1', 0), OSCHandler)
        cls.udp.app = cls.app
        for server in [cls.http, cls.udp]: threading.Thread(target=server.serve_forever, daemon=True).start()
        cls.base = 'http://127.0.0.1:' + str(cls.http.server_port)
    @classmethod
    def tearDownClass(cls):
        for server in [cls.http, cls.udp]: server.shutdown(); server.server_close()
        cls.tmp.cleanup()
    def request(self, path, data=None, content_type='application/json'):
        headers = {'Content-Type': content_type}
        request = urllib.request.Request(self.base + path, data=None if data is None else json.dumps(data).encode(), headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=3) as response: return response.status, response.read()
        except urllib.error.HTTPError as e: return e.code, e.read()
    def test_http_direct_access_and_delivery(self):
        self.assertEqual(self.request('/api/command', {'mode': 'stop'})[0], 200)
        self.assertEqual(self.request('/api/settings')[0], 200)
        self.assertEqual(self.request('/api/command', {'mode': 'stop'})[0], 200)
        state = json.loads(self.request('/api/state')[1])
        self.assertEqual(state['cue']['mode'], 'stop')
        self.assertEqual(self.request('/api/command', {'mode': 'bad'})[0], 400)
        self.assertEqual(self.request('/api/command', {'mode': 'stop'}, 'text/plain')[0], 415)
    def test_local_kiosk_can_read_public_state_but_cors_does_not_open_commands(self):
        req = urllib.request.Request(self.base + '/api/state', headers={'Origin': 'null'})
        with urllib.request.urlopen(req, timeout=3) as response:
            self.assertEqual(response.headers.get('Access-Control-Allow-Origin'), '*')
            self.assertIn('cue', json.loads(response.read()))
        req = urllib.request.Request(self.base + '/api/command', data=b'{"mode":"stop"}',
                                     headers={'Origin': 'null', 'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=3) as response:
            self.assertEqual(response.status, 200)
            self.assertIsNone(response.headers.get('Access-Control-Allow-Origin'))

    def test_update_api_accepts_no_urls_or_commands(self):
        self.assertEqual(self.request('/api/updates')[0], 200)
        for data in ({'url':'https://example.com'}, {'revision':'a'*40}, {'command':'id'}, []):
            self.assertEqual(self.request('/api/updates/install', data)[0], 400)
        self.assertEqual(self.request('/api/updates/install', {})[0], 400)

    def test_static_and_no_traversal(self):
        for path in ['/', '/display', '/admin.js', '/display.js', '/style.css']:
            self.assertEqual(self.request(path)[0], 200)
        self.assertEqual(self.request('/../server.py')[0], 404)
        self.assertEqual(self.request('/token')[0], 404)
    def test_udp_delivery_and_rejection(self):
        import time
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.sendto(osc('/show/text', 'OSC vérifié'), self.udp.server_address)
            limit = time.monotonic() + 2
            while self.app.osc_received == 0 and time.monotonic() < limit: time.sleep(.01)
            self.assertEqual(self.app.snapshot()['cue']['text'], 'OSC vérifié')
            s.sendto(osc('/show/unknown'), self.udp.server_address)
            while self.app.osc_rejected == 0 and time.monotonic() < limit: time.sleep(.01)
            self.assertEqual(self.app.osc_rejected, 1)


if __name__ == '__main__': unittest.main()
