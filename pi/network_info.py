"""Adresses locales IPv4, sans requête vers un service externe."""
import ipaddress
import json
import socket
import subprocess

def addresses():
    candidates = []
    try:
        result = subprocess.run(['ip', '-j', '-4', 'address', 'show', 'up'],
                                capture_output=True, text=True, timeout=2, check=True)
        for interface in json.loads(result.stdout):
            candidates.extend(a.get('local', '') for a in interface.get('addr_info', []) if a.get('family') == 'inet')
    except (OSError, ValueError, subprocess.SubprocessError):
        try:
            result = subprocess.run(['hostname', '-I'], capture_output=True, text=True, timeout=2, check=True)
            candidates = result.stdout.split()
        except (OSError, subprocess.SubprocessError):
            try: candidates = [entry[4][0] for entry in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)]
            except OSError: pass
    valid = set()
    for value in candidates:
        try:
            ip = ipaddress.ip_address(value)
            if ip.version == 4 and not (ip.is_loopback or ip.is_unspecified or ip.is_multicast): valid.add(str(ip))
        except ValueError: pass
    return sorted(valid, key=ipaddress.ip_address)

def identity():
    hostname = socket.gethostname().split('.')[0]
    return dict(hostname=hostname, mdns=hostname + '.local', ipv4=addresses())
