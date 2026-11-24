"""Summarize a private FX516PE config inventory offline. Never generate an unlock profile."""
import argparse
import hashlib
import json
from pathlib import Path
import re

LIMIT = 8 * 1024 * 1024
MARKER = 'fx516pe-330 config-only=1 can-unlock=0 no-mmio=1 no-prom=1 no-pci-write=1'


def summarize(raw):
    if len(raw) > LIMIT:
        raise ValueError('Capture exceeds size limit')
    text = raw.decode('ascii')
    configs = re.findall(r'^fx-config dwords=((?:[0-9a-f]{8} ){64})\r?$', text, re.M)
    if text.splitlines().count(MARKER) != 1 or len(configs) != 1:
        raise ValueError('Missing or ambiguous FX516PE inventory')
    config = [int(value, 16) for value in configs[0].split()]
    if config[0] != 0x25a010de or config[11] != 0x13dc1043 or config[2] >> 24 != 3:
        raise ValueError('Capture identity does not match this target')
    complete = re.findall(r'^capture-complete=([01])\r?$', text, re.M)
    if len(complete) != 1:
        raise ValueError('Missing or ambiguous completion marker')
    return {
        'schema_version': 1,
        'mode': 'config-inventory-only',
        'capture_sha256': hashlib.sha256(raw).hexdigest(),
        'capture_complete': complete == ['1'],
        'pci_device': f'{config[0]:08x}',
        'pci_subsystem': f'{config[11]:08x}',
        'class_revision': f'{config[2]:08x}',
        'pci_command': f'{config[1] & 0xffff:04x}',
        'memory_decode_enabled': bool(config[1] & 2),
        'bus_master_enabled': bool(config[1] & 4),
        'observed_gop_count': len(re.findall(r'^gop framebuffer=', text, re.M)),
        'ownership_graph_record_count': len(re.findall(r'^open agent=', text, re.M)),
        'bios_validated_in_efi': False,
        'can_unlock': False,
        'next_stage': 'Review private graph and exact PCI state before designing bounded deep capture.',
        'not_included': ['addresses', 'partition identifiers', 'firmware contents', 'raw graph'],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        with args.capture.open('rb') as stream:
            report = summarize(stream.read(LIMIT + 1))
    except (OSError, ValueError, UnicodeError):
        parser.exit(2, 'Capture unavailable, invalid, incomplete in structure, or outside this target.\n')
    text = json.dumps(report, indent=2) + '\n'
    if args.output:
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(text)
    print(text, end='')
    return 0 if report['capture_complete'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
