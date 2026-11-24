"""Create a new local diagnostic USB folder and ZIP. Never select or format a drive."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(output):
    output = output.absolute()
    archive = output.with_suffix('.zip')
    if (not output.parent.is_dir() or not output.parent.resolve().is_relative_to(ROOT.resolve())
            or output.exists() or output.is_symlink() or archive.exists() or archive.is_symlink()):
        raise ValueError('Choose a new local folder inside this checkout; no existing folder or ZIP is replaced.')
    manifest_path = HERE / 'build/manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('mode') != 'fx516pe-330-config-inventory-return-to-firmware':
        raise ValueError('Not the inventory build')
    for key in ('can_unlock', 'can_read_mmio', 'can_dump_prom', 'can_write_pci',
                'can_release_drivers', 'hardware_tested', 'bios_validated_in_efi'):
        if manifest.get(key) is not False:
            raise ValueError('Invalid diagnostic capability flags')
    binary = HERE / 'build/BOOTX64.EFI'
    if digest(binary) != manifest['pe']['sha256']:
        raise ValueError('EFI changed since inspection; rebuild')
    sources = []
    for name, expected in manifest['sources'].items():
        relative = Path(name)
        source = ROOT / relative
        if (relative.is_absolute() or '..' in relative.parts
                or not source.resolve().is_relative_to(ROOT.resolve()) or source.is_symlink()
                or not source.is_file() or digest(source) != expected):
            raise ValueError('Source changed or is invalid: rebuild before packaging')
        sources.append((name, source))
    with tempfile.TemporaryDirectory(prefix='fx516pe-package-', dir=output.parent) as temporary:
        stage = Path(temporary) / 'package'
        boot = stage / 'EFI/BOOT'
        boot.mkdir(parents=True)
        shutil.copyfile(binary, boot / 'BOOTX64.EFI')
        shutil.copyfile(manifest_path, stage / 'manifest.json')
        shutil.copyfile(HERE / 'README.es.md', stage / 'LEEME.es.md')
        for name, source in sources:
            destination = stage / 'SOURCE' / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            if digest(destination) != manifest['sources'][name]:
                raise ValueError('Source changed during packaging')
        for name, source in [('LICENSE', ROOT / 'LICENSE'),
                             ('EDK2-LICENSE.txt', ROOT / 'deps/edk2/License.txt'),
                             ('THIRD_PARTY_NOTICES.md', ROOT / 'THIRD_PARTY_NOTICES.md')]:
            shutil.copyfile(source, stage / name)
        if digest(boot / 'BOOTX64.EFI') != manifest['pe']['sha256']:
            raise ValueError('EFI changed during packaging')
        files = sorted(item for item in stage.rglob('*') if item.is_file())
        (stage / 'SHA256SUMS.txt').write_text(''.join(digest(item) + '  ' + item.relative_to(stage).as_posix()
                                                    + '\n' for item in files), encoding='utf-8')
        staged_zip = Path(temporary) / 'package.zip'
        with zipfile.ZipFile(staged_zip, 'x', zipfile.ZIP_DEFLATED) as stream:
            for file in sorted(item for item in stage.rglob('*') if item.is_file()):
                stream.write(file, file.relative_to(stage).as_posix())
        if output.exists() or archive.exists():
            raise ValueError('Output appeared during preparation')
        stage.rename(output)
        staged_zip.rename(archive)
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE / 'usb-package')
    args = parser.parse_args()
    print('Created local package:', prepare(args.output))
    print('No USB, partition, boot entry or firmware setting was changed.')


if __name__ == '__main__':
    main()
