"""Build and test the non-arming config inventory with installed MSVC. Files only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFINES = ['GU_DIAGNOSTIC_ONLY', 'GU_DIAGNOSTIC_PROBE', 'GU_PROBE_GENERIC']
FORBIDDEN = ['GU_FULL_UNLOCK', 'GU_EXPERIMENTAL_3090', 'GU_UEFI_PORT',
             'GU_INTERNAL_BOOT', 'GU_CONSOLE_PREPARE', 'GU_AUTOMATIC_BOOT',
             'GU_HEADLESS_RESEARCH', 'GU_PROBE_PARENT_BASELINE', 'GU_PROBE_DUMP_PROM']


def run(argv, env):
    search_path = next((v for k, v in env.items() if k.lower() == 'path'), '')
    argv = list(argv)
    argv[0] = shutil.which(str(argv[0]), path=search_path) or argv[0]
    result = subprocess.run([str(x) for x in argv], env=env, cwd=ROOT,
                            capture_output=True, text=True, errors='replace')
    if result.returncode:
        raise RuntimeError('Build/test failed:\n' + result.stdout + result.stderr)
    return result.stdout


def environment(vcvars):
    # Read the compiler environment into memory; never print it or persist it.
    if any(char in str(vcvars) for char in ('"', '&', '|', '<', '>')):
        raise ValueError('Invalid vcvars path')
    result = subprocess.run('cmd.exe /d /s /c ""' + str(vcvars) + '" >nul && set"',
                            capture_output=True, text=True, errors='replace')
    if result.returncode:
        raise RuntimeError('MSVC environment could not be initialized.')
    return dict(line.split('=', 1) for line in result.stdout.splitlines()
                if '=' in line and not line.startswith('='))


def inspect_pe(path):
    data = path.read_bytes()
    if data[:2] != b'MZ':
        raise ValueError('Missing DOS header')
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    if data[pe:pe+4] != b'PE\0\0':
        raise ValueError('Missing PE signature')
    machine, sections = struct.unpack_from('<HH', data, pe+4)
    opt = pe+24
    magic = struct.unpack_from('<H', data, opt)[0]
    subsystem = struct.unpack_from('<H', data, opt+68)[0]
    imports = struct.unpack_from('<II', data, opt+112+8)
    relocations = struct.unpack_from('<II', data, opt+112+5*8)
    entry = struct.unpack_from('<I', data, opt+16)[0]
    if machine != 0x8664 or magic != 0x20b or subsystem != 10 or imports != (0, 0):
        raise ValueError('Not a freestanding x64 EFI application')
    if not all(relocations) or not entry or not sections:
        raise ValueError('Missing relocations, entry point or sections')
    return {'machine': 'x64', 'subsystem': 'efi_application', 'imports': 0,
            'relocation_bytes': relocations[1], 'entry_rva': entry,
            'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vcvars', type=Path, default=Path(
        r'C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat'))
    args = parser.parse_args()
    if sys.platform != 'win32' or not args.vcvars.is_file():
        parser.error('Requires Windows with installed x64 MSVC; pass --vcvars if needed.')
    out = HERE / 'build'
    out.mkdir(exist_ok=True)
    env = environment(args.vcvars)
    print(run([sys.executable, '-I', HERE / 'test_python_tools.py'], env).strip())
    include = ROOT / 'deps/edk2/MdePkg/Include'
    search_path = next((v for k, v in env.items() if k.lower() == 'path'), '')
    compiler = shutil.which('cl.exe', path=search_path)
    if not compiler:
        raise RuntimeError('The MSVC environment has no cl.exe.')
    base = [compiler, '/nologo', '/std:c11', '/W3', '/D_CRT_SECURE_NO_WARNINGS',
            '/I' + str(include), '/I' + str(include / 'X64')]
    defines = ['/D' + x for x in DEFINES]
    host = out / 'test-inventory.exe'
    output = run([*base, *defines, HERE / 'test_inventory.c', HERE / 'inventory_probe.c',
                  '/Fo' + str(out) + os.sep, '/Fe' + str(host)], env)
    print(run([host], env).strip())
    entry_test = out / 'test-entry.exe'
    run([*base, *defines, HERE / 'test_entry.c',
         '/Fo' + str(out) + os.sep, '/Fe' + str(entry_test)], env)
    print(run([entry_test], env).strip())
    source = out / 'policy-check.c'
    source.write_text('#include "' + (HERE / 'inventory_policy.h').as_posix() + '"\n', encoding='ascii')
    cases = [[x for x in defines if x != '/D' + missing] for missing in DEFINES]
    cases += [defines + ['/D' + bad] for bad in FORBIDDEN]
    for flags in cases:
        result = subprocess.run([*base, *flags, '/Zs', str(source)], env=env,
                                capture_output=True)
        if result.returncode == 0:
            raise RuntimeError('Write-capable or incomplete define set was accepted.')
    print('PASS', len(cases), 'compile-time refusal cases')
    sources = [HERE / 'entry.c', HERE / 'inventory_probe.c',
               ROOT / 'internal-boot/boot/diagnostic.c', ROOT / 'internal-boot/efi_runtime.c']
    objects = []
    for source in sources:
        obj = out / (source.stem + '.obj')
        run([*base, *defines, '/c', '/O1', '/GS-', '/Zl', '/Oi-', str(source),
             '/Fo' + str(obj)], env)
        objects.append(obj)
    efi = out / 'BOOTX64.EFI'
    run(['link.exe', '/nologo', '/nodefaultlib', '/subsystem:efi_application',
         '/entry:efi_main', '/machine:x64', '/dynamicbase:no', '/fixed:no', '/nxcompat:no', '/base:0',
         '/opt:ref', '/opt:icf', '/incremental:no', '/Brepro',
         '/map:' + str(out / 'inventory.map'), '/out:' + str(efi), *objects], env)
    pe = inspect_pe(efi)
    inputs = set(sources + [HERE / 'target.json', HERE / 'README.es.md'])
    inputs.update(item for item in HERE.iterdir() if item.suffix in ('.c', '.h', '.py'))
    for folder in (HERE, ROOT / 'internal-boot/boot', ROOT / 'internal-boot/unlock', include):
        inputs.update(folder.glob('*.h') if folder != include else folder.rglob('*.h'))
    manifest = {'schema_version': 1, 'mode': 'fx516pe-330-config-inventory-return-to-firmware',
                'can_unlock': False, 'can_read_mmio': False, 'can_dump_prom': False,
                'can_write_pci': False, 'can_release_drivers': False,
                'hardware_tested': False, 'bios_validated_in_efi': False,
                'defines': DEFINES, 'pe': pe,
                'compiler': compiler,
                'sources': {str(s.relative_to(ROOT)).replace('\\', '/'):
                            hashlib.sha256(s.read_bytes()).hexdigest() for s in sorted(inputs)}}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print('Built and inspected', efi.name, pe['bytes'], 'bytes; hardware untested.')


if __name__ == '__main__':
    main()
