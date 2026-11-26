import importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
R=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('cleanup_continuacao',R/'scripts/limpar-continuacao-controlado.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class CleanupContinuacaoTests(unittest.TestCase):
    def test_missing_explicit_flag_never_opens_report(self):
        with patch.object(sys,'argv',['cleanup','--plan','/missing','--sha256','0'*64]),patch.object(m.os,'geteuid',return_value=0),patch.object(m.os,'open') as op:
            with self.assertRaises(ValueError):m.main()
            op.assert_not_called()
    def test_unprivileged_cannot_execute(self):
        with patch.object(sys,'argv',['cleanup','--plan','/missing','--sha256','0'*64,'--execute-authorized']),patch.object(m.os,'geteuid',return_value=1000),patch.object(m.os,'open') as op:
            with self.assertRaises(ValueError):m.main()
            op.assert_not_called()
    def test_changed_plan_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'plan.json';p.write_text('{}')
            with self.assertRaisesRegex(ValueError,'Plan changed'):m.load(p,'0'*64)
    def test_incomplete_scope_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'plan.json';p.write_text(json.dumps({'operation':'continuacao-exact-43','candidates':[]}))
            with self.assertRaisesRegex(ValueError,'Scope mismatch'):m.load(p,m.sha(p))
