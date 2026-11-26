import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from pi.network_info import addresses, identity

class NetworkInfoTests(unittest.TestCase):
    def test_multiple_interfaces_deduplicated_no_loopback(self):
        data = [dict(addr_info=[dict(family='inet',local=ip) for ip in
                ['127.0.0.1','192.168.1.20','10.0.0.4','192.168.1.20','::1','bad']])]
        with patch('pi.network_info.subprocess.run',return_value=SimpleNamespace(stdout=json.dumps(data))):
            self.assertEqual(addresses(),['10.0.0.4','192.168.1.20'])
    def test_fallback_without_ip_tool(self):
        with patch('pi.network_info.subprocess.run',side_effect=[FileNotFoundError(),SimpleNamespace(stdout='192.168.1.30 127.0.0.1 fe80::1')]):
            self.assertEqual(addresses(),['192.168.1.30'])
    def test_offline_and_mdns_name(self):
        with patch('pi.network_info.subprocess.run',side_effect=OSError()), patch('pi.network_info.socket.getaddrinfo',side_effect=OSError()), patch('pi.network_info.socket.gethostname',return_value='stopshow.local'):
            self.assertEqual(identity(),dict(hostname='stopshow',mdns='stopshow.local',ipv4=[]))
