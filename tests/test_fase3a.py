"""Testes com amostras; nenhum hipervisor é executado."""
import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


diag = load('diag', 'scripts/diagnostico-virtualizacao.py')
report = load('report', 'scripts/validar-relatorio-iso.py')


class DiagnosticTests(unittest.TestCase):
    def test_extensions_hidden_and_heterogeneous(self):
        self.assertEqual(diag.cpu_extensions('flags : hypervisor sse'), [])
        self.assertEqual(diag.cpu_extensions('flags : vmx sse\nflags : sse'), [])
        self.assertEqual(diag.cpu_extensions('flags : vmx sse'), ['vmx'])
        self.assertEqual(diag.cpu_extensions('flags : svm sse'), ['svm'])

    def test_device_alone_is_not_nested_virtualization(self):
        result = diag.assess([], True, True, '/usr/bin/qemu', 16 * 1024**3)
        self.assertFalse(result['kvm_precondicoes_observadas'])
        self.assertTrue(result['bloqueios_qemu_local'])

    def test_kvm_permission_and_ram_blockers(self):
        result = diag.assess(['vmx'], True, False, '/usr/bin/qemu', 4 * 1024**3)
        self.assertFalse(result['kvm_precondicoes_observadas'])
        self.assertEqual(len(result['bloqueios_qemu_local']), 2)

    def test_present_preconditions_are_not_execution_proof(self):
        result = diag.assess(['svm'], True, True, '/usr/bin/qemu', 16 * 1024**3)
        self.assertTrue(result['kvm_precondicoes_observadas'])
        self.assertEqual(result['bloqueios_qemu_local'], [])
        self.assertIn('nenhum ioctl', result['limite'])


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.template = json.loads((ROOT / 'tests/modelo-relatorio-iso.json').read_text())
        self.complete = copy.deepcopy(self.template)
        for firmware, run in self.complete['execucoes'].items():
            run['ambiente'] = {name: 'amostra' for name in report.ENVIRONMENT}
            run['ambiente']['vm'] = 'vm-' + firmware
            for check in run['criterios'].values():
                check.update(status='aprovado', evidencia='Amostra fictícia exclusiva do teste unitário')

    def test_pending_template_cannot_pass(self):
        self.assertTrue(report.validate(self.template))

    def test_complete_and_separate_runs(self):
        self.assertEqual(report.validate(self.complete), [])

    def test_wrong_hash_or_missing_firmware(self):
        self.complete['sha256'] = '0' * 64
        self.assertTrue(report.validate(self.complete))
        del self.complete['execucoes']['uefi']
        self.assertTrue(report.validate(self.complete))

    def test_evidence_and_reboot_are_mandatory(self):
        check = self.complete['execucoes']['bios']['criterios']['boot_sem_iso']
        check['evidencia'] = ''
        self.assertTrue(report.validate(self.complete))
        check.update(evidencia='amostra', status='falhou')
        self.assertTrue(report.validate(self.complete))

    def test_same_vm_and_malformed_data_fail(self):
        self.complete['execucoes']['uefi']['ambiente']['vm'] = 'vm-bios'
        self.assertTrue(report.validate(self.complete))
        for value in ([], None, {'execucoes': []}):
            self.assertTrue(report.validate(value))
        self.complete['execucoes']['bios']['criterios'] = []
        self.assertTrue(report.validate(self.complete))

    def test_cli_rejects_invalid_json_and_pending_report(self):
        with tempfile.TemporaryDirectory() as folder:
            invalid = Path(folder) / 'invalid.json'
            invalid.write_text('{invalid')
            for path in (invalid, ROOT / 'tests/modelo-relatorio-iso.json'):
                result = subprocess.run([sys.executable, str(ROOT / 'scripts/validar-relatorio-iso.py'), str(path)], capture_output=True)
                self.assertEqual(result.returncode, 1)


if __name__ == '__main__':
    unittest.main()
