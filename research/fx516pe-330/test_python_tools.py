"""Offline identity and capture regressions; no GPU or firmware access."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import tempfile
import hashlib

HERE = Path(__file__).resolve().parent


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


collector = module('fx_collector', 'collect_windows.py')
review = module('fx_review', 'review_capture.py')
packaging = module('fx_packaging', 'prepare_package.py')
target = json.loads((HERE / 'target.json').read_text())


class ResearchTests(unittest.TestCase):
    def inventory(self):
        return {'registry': {'system': {'BaseBoardProduct': 'FX516PE', 'BIOSVersion': 'FX516PE.330'}},
                'gpus': [{'pci.device_id': '0x25A010DE', 'pci.sub_device_id': '0x13DC1043',
                          'vbios_version': '94.07.42.00.3a', 'memory.total': '4096'}]}

    def capture(self, command=0, complete=1):
        words = [0] * 64
        words[0], words[1], words[2], words[11] = 0x25a010de, command, 0x030000a1, 0x13dc1043
        return (review.MARKER + '\r\nfx-config dwords=' + ''.join(f'{word:08x} ' for word in words)
                + '\r\ncapture-complete=' + str(complete) + '\r\n').encode('ascii')

    def test_exact_windows_identity(self):
        self.assertTrue(collector.matches_target(self.inventory(), target))
        for key, value in [('pci.device_id', '0x25A210DE'), ('pci.sub_device_id', '0x13FC1043'),
                           ('vbios_version', '94.07.42.00.00'), ('memory.total', '8192')]:
            changed = self.inventory()
            changed['gpus'][0][key] = value
            self.assertFalse(collector.matches_target(changed, target))

    def test_other_bios_board_or_multiple_gpus(self):
        for key in ('BaseBoardProduct', 'BIOSVersion'):
            changed = self.inventory()
            changed['registry']['system'][key] = 'other'
            self.assertFalse(collector.matches_target(changed, target))
        changed = self.inventory()
        changed['gpus'] *= 2
        self.assertFalse(collector.matches_target(changed, target))

    def test_decode_state_is_observed_and_never_grants_unlock(self):
        for command in range(8):
            report = review.summarize(self.capture(command))
            self.assertEqual(report['memory_decode_enabled'], bool(command & 2))
            self.assertEqual(report['bus_master_enabled'], bool(command & 4))
            self.assertFalse(report['can_unlock'])
            self.assertFalse(report['bios_validated_in_efi'])

    def test_capture_summary_does_not_echo_private_records(self):
        raw = self.capture() + b'private partition marker=PRIVATE_PARTITION_ID\r\n'
        self.assertNotIn('PRIVATE_PARTITION_ID', json.dumps(review.summarize(raw)))

    def test_incomplete_capture_does_not_become_complete(self):
        report = review.summarize(self.capture(complete=0))
        self.assertFalse(report['capture_complete'])
        self.assertFalse(report['can_unlock'])

    def test_foreign_truncated_duplicate_and_oversized_capture_refused(self):
        original = self.capture()
        invalid = [original.replace(b'25a010de', b'25a210de'), original.replace(b'13dc1043', b'13fc1043'),
                   original.replace(b'030000a1', b'020000a1'), original[:100], original + original,
                   b'x' * (review.LIMIT + 1), original.replace(b'capture-complete=1', b'capture-complete=2')]
        for raw in invalid:
            with self.assertRaises(ValueError):
                review.summarize(raw)

    def test_package_refuses_changed_binary_sources_and_existing_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            here = root / 'research/fx516pe-330'
            build = here / 'build'
            build.mkdir(parents=True)
            binary = build / 'BOOTX64.EFI'
            binary.write_bytes(b'synthetic test binary; never boot')
            source = root / 'sample.c'
            source.write_text('/* fixture */\n')
            manifest = {'mode': 'fx516pe-330-config-inventory-return-to-firmware',
                        'pe': {'sha256': hashlib.sha256(binary.read_bytes()).hexdigest()},
                        'sources': {'sample.c': hashlib.sha256(source.read_bytes()).hexdigest()}}
            for key in ('can_unlock', 'can_read_mmio', 'can_dump_prom', 'can_write_pci',
                        'can_release_drivers', 'hardware_tested', 'bios_validated_in_efi'):
                manifest[key] = False
            record = build / 'manifest.json'
            record.write_text(json.dumps(manifest))
            with patch.object(packaging, 'HERE', here), patch.object(packaging, 'ROOT', root):
                binary.write_bytes(b'changed')
                with self.assertRaises(ValueError):
                    packaging.prepare(here / 'package')
                binary.write_bytes(b'synthetic test binary; never boot')
                source.write_text('changed')
                with self.assertRaises(ValueError):
                    packaging.prepare(here / 'package')
                occupied = here / 'occupied'
                occupied.mkdir()
                with self.assertRaises(ValueError):
                    packaging.prepare(occupied)
                manifest['sources'] = {'../outside': '0' * 64}
                record.write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    packaging.prepare(here / 'package')

    def test_package_refuses_unlock_capability(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            here = root / 'research'
            (here / 'build').mkdir(parents=True)
            (here / 'build/manifest.json').write_text(json.dumps({
                'mode': 'fx516pe-330-config-inventory-return-to-firmware', 'can_unlock': True}))
            with patch.object(packaging, 'HERE', here), patch.object(packaging, 'ROOT', root):
                with self.assertRaises(ValueError):
                    packaging.prepare(here / 'package')


if __name__ == '__main__':
    unittest.main()
