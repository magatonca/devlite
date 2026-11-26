"""Controlador testado com mocks: nenhuma ISO ou operação privilegiada real."""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pipeline.devlite.customize.executor_contract import ROOT
from pipeline.devlite.customize.manifest import SpecError
spec=importlib.util.spec_from_file_location('controlled_iso',ROOT/'scripts/gerar-isos-controladas.py')
control=importlib.util.module_from_spec(spec);spec.loader.exec_module(control)


class IsoControlTests(unittest.TestCase):
    def exercise(self,*,failure=False,two=False,seed='0',active=False):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as folder:
            root=Path(folder);(root/'config').mkdir();job=root/'job';job.mkdir();config=root/'config/projeto.json'
            config.write_text(json.dumps({'iso_final_autorizada':False,'executor_autorizado':active,'preserve':'value'}))
            with patch.object(control,'ROOT',root),patch.object(control,'ordinary'),patch.dict(os.environ,{'PYTHONHASHSEED':seed}),patch.object(control,'read',return_value=(job,{})),patch.object(control,'ready_layers'),patch.object(control,'build',side_effect=SpecError('fixture failure') if failure else None,return_value=job/'first-report.json') as build,patch.object(control,'reproduce',return_value=job/'reproducibility.json') as reproduce:
                if failure or seed!='0' or active:
                    with self.assertRaises(SpecError):control.run(job,'proof',two)
                else:
                    report=json.loads(control.run(job,'proof',two).read_text());self.assertEqual(report['status'],'completed');self.assertTrue(report['iso_gate_restored_false'])
                flags=json.loads(config.read_text());self.assertFalse(flags['iso_final_autorizada']);self.assertEqual(flags['preserve'],'value')
                if seed!='0' or active:build.assert_not_called()
                elif not failure:build.assert_called_once_with(job,'proof')
                if two and not failure:reproduce.assert_called_once_with(job,'proof',job/'first-report.json')
                else:reproduce.assert_not_called()
    def test_single_build_restores_permission(self):self.exercise()
    def test_second_build_uses_exact_first_report(self):self.exercise(two=True)
    def test_failure_restores_permission_and_preserves_evidence(self):self.exercise(failure=True,two=True)
    def test_randomized_hash_order_is_rejected(self):self.exercise(seed='random')
    def test_active_executor_blocks_before_iso(self):self.exercise(active=True)
    def test_real_nonroot_precondition_remains_present(self):
        with patch.object(control,'ordinary',side_effect=SpecError('requires magaton')),patch.object(control,'build') as build:
            with self.assertRaises(SpecError):control.run(ROOT/'work/absent','proof')
            build.assert_not_called()
