import importlib.util,unittest
from pathlib import Path
from unittest.mock import patch
R=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('modern_iso_test',R/'scripts/gerar-iso-modern-controlada.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ModernIsoControllerTests(unittest.TestCase):
 def test_no_implicit_authorization_before_access_or_generation(self):
  with patch.object(m,'ordinary'),patch.object(m,'layers') as layers:
   with self.assertRaises(ValueError):m.run(None,None,False)
   layers.assert_not_called()
 def test_no_root_generation(self):
  with patch.object(m.os,'getuid',return_value=1000),patch.object(m.os,'geteuid',return_value=0):
   with self.assertRaises(ValueError):m.ordinary()
 def test_single_claim_never_overwrites(self):
  import tempfile
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'claim.json';m.save(p,{'build_count':1})
   with self.assertRaises(FileExistsError):m.save(p,{'build_count':2})
 def test_nonzero_hashseed_blocks_before_layers(self):
  with patch.object(m,'ordinary'),patch.dict(m.os.environ,{'PYTHONHASHSEED':'1'}),patch.object(m,'layers') as layers:
   with self.assertRaises(ValueError):m.run(None,None,True)
   layers.assert_not_called()
