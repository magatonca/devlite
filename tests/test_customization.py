"""Testes de preparação com fixtures, sem rede, mounts ou instalações."""
import base64
import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.devlite.customize.manifest import resolve, SpecError
from pipeline.devlite.customize.settings import render
from pipeline.devlite.customize.layers import audit, strategy
from pipeline.devlite.customize.planner import make_plan, export_plan, lock_blockers, apt_metadata
from pipeline.devlite.customize.integrity import verify_payload, verify_export


class CustomizationTests(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads((ROOT / 'packages/selection.json').read_text())
        self.settings = json.loads((ROOT / 'config/customization.json').read_text())

    def test_default_selection_and_dependency_order(self):
        items = resolve(self.spec)
        keys = [item['id'] for item in items]
        self.assertEqual(len(keys), 47)
        for item in items:
            for dependency in item['depends_on']:
                self.assertLess(keys.index(dependency), keys.index(item['id']))

    def test_dependency_closure_crosses_categories(self):
        items = resolve(self.spec, ['redes'])
        self.assertIn('network-manager', [item['id'] for item in items])
        self.assertNotIn('vscode', [item['id'] for item in items])

    def test_duplicate_and_malformed_package_rejected(self):
        for field, value in (('id', 'ca-certificates'), ('package', 'php; touch /tmp/x')):
            changed = copy.deepcopy(self.spec)
            changed['categories']['desenvolvimento'][0][field] = value
            with self.assertRaises(SpecError):
                resolve(changed)

    def test_unknown_dependency_and_cycle(self):
        changed = copy.deepcopy(self.spec)
        changed['categories']['sistema'][0]['depends_on'] = ['missing']
        with self.assertRaises(SpecError):
            resolve(changed)
        changed['categories']['sistema'][0]['depends_on'] = ['ca-certificates']
        with self.assertRaises(SpecError):
            resolve(changed)

    def test_architecture_and_provider_conflicts(self):
        changed = copy.deepcopy(self.spec)
        changed['architecture'] = 'arm64'
        with self.assertRaises(SpecError):
            resolve(changed)
        changed = copy.deepcopy(self.spec)
        changed['categories']['sistema'].append({'id': 'nodejs', 'package': 'nodejs', 'provider': 'ubuntu',
                                                  'depends_on': [], 'scope': 'installed-and-live'})
        with self.assertRaises(SpecError):
            resolve(changed)

    def test_keyboard_locale_timezone_and_xfce_are_rendered(self):
        bundle = render(self.settings)
        self.assertIn('XKBMODEL="abnt2"', bundle['files']['etc/default/keyboard']['content'])
        self.assertIn('LANG=pt_BR.UTF-8', bundle['files']['etc/default/locale']['content'])
        self.assertEqual(bundle['files']['etc/localtime']['target'], '../usr/share/zoneinfo/America/Sao_Paulo')
        for name, entry in bundle['files'].items():
            if name.endswith('.xml'):
                ET.fromstring(entry['content'])
        self.assertIn('keyboard-configuration/layoutcode=br', bundle['actions']['live_boot_arguments'])
        self.assertNotIn('etc/os-release', bundle['files'])

    def test_unsafe_settings_and_privilege_groups_rejected(self):
        for field, value in (('timezone', '../../etc/passwd'), ('locale', 'pt_BR; sh')):
            changed = copy.deepcopy(self.settings)
            changed[field] = value
            with self.assertRaises(SpecError):
                render(changed)
        self.settings['services']['automatic_docker_group'] = True
        with self.assertRaises(SpecError):
            render(self.settings)

    def test_layer_audit_detects_shadowed_dpkg_and_configuration(self):
        base = '-rw-r--r-- root/root 1 date squashfs-root/var/lib/dpkg/status\n'
        live = base + '-rw-r--r-- root/root 1 date squashfs-root/etc/default/keyboard\n'
        result = audit(base, live)
        self.assertTrue(result['dpkg_status_shadowed'])
        self.assertIn('etc/default/keyboard', result['live_configuration_paths'])
        self.assertTrue(result['xattrs_and_opaque_directories_audit_required'])
        with self.assertRaises(SpecError):
            audit('', live)

    def test_layer_stages_are_ordered_and_do_not_execute(self):
        seen = set()
        for stage in strategy():
            self.assertTrue(set(stage['after']) <= seen)
            self.assertNotIn('argv', stage)
            seen.add(stage['id'])
        self.assertIn('rebase-live', seen)

    def test_default_plan_never_runs_commands_and_cannot_apply(self):
        with patch('subprocess.run', side_effect=AssertionError('Nenhum processo permitido')):
            plan = make_plan(ROOT)
        self.assertFalse(plan['ready_to_apply'])
        self.assertTrue(plan['blockers'])
        self.assertIsNone(plan['apt_cache'])

    def test_lock_cannot_mix_external_and_ubuntu_node(self):
        lock = json.loads((ROOT / 'config/customization-lock.json').read_text())
        lock['apt_packages']['nodejs'] = {}
        sources = json.loads((ROOT / 'packages/sources.json').read_text())
        with self.assertRaises(SpecError):
            lock_blockers(lock, resolve(self.spec), sources, self.spec['forbidden_apt'])

    def test_payload_hash_and_sri_reject_tampering(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'payload'
            path.write_bytes(b'fixture')
            sha = hashlib.sha256(b'fixture').hexdigest()
            sri = 'sha512-' + base64.b64encode(hashlib.sha512(b'fixture').digest()).decode()
            self.assertEqual(verify_payload(path, sha, sri)['bytes'], 7)
            with self.assertRaises(SpecError):
                verify_payload(path, sha, 'sha512-AAAA')
            path.write_bytes(b'changed')
            with self.assertRaises(SpecError):
                verify_payload(path, sha, sri)

    def test_export_integrity_and_tampering(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'work').mkdir()
            plan = make_plan(ROOT)
            with patch('subprocess.run', side_effect=AssertionError('Nenhum processo permitido')):
                workspace = export_plan(root, plan)
                self.assertEqual(verify_export(workspace)['files_verified'], 11)
            (workspace / 'overlay/etc/default/locale').write_text('changed')
            with self.assertRaises(SpecError):
                verify_export(workspace)

    def test_export_rejects_traversal_without_modifying_outside(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'work').mkdir()
            sentinel = root / 'sentinel'
            sentinel.write_text('keep')
            plan = make_plan(ROOT)
            plan['settings_bundle']['files'] = {'../../sentinel': {'kind': 'text', 'content': 'bad', 'mode': 420}}
            with self.assertRaises(SpecError):
                export_plan(root, plan)
            self.assertEqual(sentinel.read_text(), 'keep')

    def test_apt_queries_are_read_only_and_preserve_architecture(self):
        from types import SimpleNamespace
        entries = [{'package': 'git', 'provider': 'ubuntu'}]
        policy = 'git:\n  Candidate: 1.0\n     1.0 500\n        500 https://archive.ubuntu.com noble/main amd64 Packages\n'
        shown = 'Package: git\nVersion: 1.0\nArchitecture: amd64\nSection: vcs\nDepends: libc6\n'
        with patch('subprocess.run', side_effect=[SimpleNamespace(stdout=policy), SimpleNamespace(stdout=shown)]) as calls:
            result = apt_metadata(entries)
        self.assertEqual([call.args[0][:2] for call in calls.call_args_list], [['apt-cache', 'policy'], ['apt-cache', 'show']])
        self.assertEqual(result['git']['architecture'], 'amd64')
        self.assertTrue(result['git']['noble_archive_visible'])

    def test_foreign_suite_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ('packages/selection.json', 'packages/sources.json', 'config/customization.json', 'config/customization-lock.json'):
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
            source = root / 'packages/sources.json'
            value = json.loads(source.read_text())
            value['sources']['ubuntu']['suites'] = ['jammy']
            source.write_text(json.dumps(value))
            with self.assertRaises(SpecError):
                make_plan(root)

    def test_malformed_external_lock_fails_closed(self):
        lock = json.loads((ROOT / 'config/customization-lock.json').read_text())
        lock['external_artifacts']['typescript'] = None
        sources = json.loads((ROOT / 'packages/sources.json').read_text())
        with self.assertRaises(SpecError):
            lock_blockers(lock, resolve(self.spec), sources, self.spec['forbidden_apt'])

    def test_cli_has_no_apply_mode(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/planejar-personalizacao.py'), '--apply'], capture_output=True)
        self.assertEqual(result.returncode, 2)


if __name__ == '__main__':
    unittest.main()
