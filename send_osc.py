#!/usr/bin/env python3
"""Client OSC de test sans dépendance. Voir COMPANION.md."""
import argparse
from pathlib import Path
import socket
import struct


def string(value):
    data = value.encode('utf8') + b'\0'
    return data + b'\0' * (-len(data) % 4)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('host')
    p.add_argument('address', choices=['/show/' + m for m in ('text', 'stop', 'black', 'clock', 'timer', 'countdown', 'test', 'keepalive')])
    p.add_argument('value', nargs='?')
    p.add_argument('--port', type=int, default=9000)
    p.add_argument('--token-file', required=True)
    args = p.parse_args()
    key = Path(args.token_file).read_text().strip()
    tags, payload = ',s', string(key)
    if args.value is not None:
        if args.address == '/show/timer':
            tags += 'f'
            payload += struct.pack('>f', float(args.value))
        else:
            tags += 's'
            payload += string(args.value)
    packet = string(args.address) + string(tags) + payload
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(packet, (args.host, args.port))
    print('Paquet OSC envoyé. Vérifiez l’écran ; UDP ne fournit pas d’accusé de réception.')


if __name__ == '__main__':
    main()
