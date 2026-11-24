"""Collect selected public model fields locally; never authorize a GPU unlock."""
import argparse
import csv
import ctypes
import datetime
import io
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
FIELDS = ('name,pci.device_id,pci.sub_device_id,vbios_version,memory.total,'
          'memory.used,memory.free,driver_version,compute_cap,temperature.gpu,'
          'power.draw,power.default_limit,clocks.current.sm,clocks.max.sm,pstate')


def registry_fields():
    import winreg
    def read(key, names):
        result = {}
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as opened:
                for name in names:
                    try:
                        value = winreg.QueryValueEx(opened, name)[0]
                        result[name] = value if isinstance(value, (str, int)) else None
                    except OSError:
                        result[name] = None
        except OSError:
            result = dict.fromkeys(names)
        return result
    return {
        'system': read(r'HARDWARE\DESCRIPTION\System\BIOS',
                       ('SystemProductName', 'BaseBoardProduct', 'BIOSVersion')),
        'windows': read(r'SOFTWARE\Microsoft\Windows NT\CurrentVersion',
                        ('ProductName', 'DisplayVersion', 'CurrentBuild', 'UBR')),
        'secure_boot': read(r'SYSTEM\CurrentControlSet\Control\SecureBoot\State',
                            ('UEFISecureBootEnabled',)),
    }


def smi(arguments):
    executable = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/nvidia-smi.exe'
    result = subprocess.run([str(executable), *arguments], capture_output=True, timeout=20)
    if result.returncode:
        raise RuntimeError('NVIDIA query failed; no raw stderr included.')
    return result.stdout.decode('utf-8-sig').strip()


def gpu_rows(text):
    reader = csv.reader(io.StringIO(text))
    return [dict(zip(FIELDS.split(','), [v.strip() for v in row])) for row in reader]


def matches_target(report, target):
    system = report['registry']['system']
    gpus = report['gpus']
    if len(gpus) != 1:
        return False
    gpu = gpus[0]
    return (system.get('BaseBoardProduct') == target['baseboard_product']
            and system.get('BIOSVersion') == target['bios_version']
            and gpu.get('pci.device_id', '').lower() == '0x' + target['pci_device']
            and gpu.get('pci.sub_device_id', '').lower() == '0x' + target['pci_subsystem']
            and gpu.get('vbios_version', '').lower() == target['vbios_version'].lower()
            and gpu.get('memory.total') == str(target['vram_mib']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if sys.platform != 'win32':
        parser.error('Windows is required for collection.')
    target = json.loads((HERE / 'target.json').read_text(encoding='utf-8'))
    report = {
        'schema_version': 1,
        'collected_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'registry': registry_fields(),
        'gpus': gpu_rows(smi(['--query-gpu=' + FIELDS, '--format=csv,noheader,nounits'])),
        'can_unlock': False,
        'preboot_validation': 'pending',
        'not_collected': ['serials', 'hostname', 'username', 'UUIDs', 'recovery keys',
                          'PROM', 'firmware images', 'partition GUIDs'],
    }
    report['expected_windows_identity_matches'] = matches_target(report, target)
    output = json.dumps(report, indent=2, ensure_ascii=True) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(output)
    print(output, end='')
    return 0 if report['expected_windows_identity_matches'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
