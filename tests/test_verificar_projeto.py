import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/verificar-projeto.py'
SPEC = importlib.util.spec_from_file_location('verificar_projeto', SCRIPT)
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)


class ProjectBuildGateTests(unittest.TestCase):
    def test_current_project_config_keeps_build_disabled(self):
        config = json.loads((ROOT / 'config/projeto.json').read_text())
        self.assertEqual(VERIFIER.validate_build_gate(config), [])

    def test_historical_authorization_text_cannot_enable_builds(self):
        for phase, subphase in ((3, 'B'), (4, 'B.1')):
            with self.subTest(phase=phase, subphase=subphase):
                config = {
                    'fase': phase,
                    'subfase': subphase,
                    'build_habilitado': True,
                    'autorizacao_build': (
                        'Usuário autorizou ISO experimental em uma etapa anterior'
                    ),
                    'operacoes_privilegiadas_autorizadas': False,
                }
                self.assertEqual(
                    VERIFIER.validate_build_gate(config),
                    ['build_habilitado deve ser false; builds exigem aprovação operacional separada'],
                )

    def test_gate_requires_boolean_false_not_a_truthy_string(self):
        for value in (None, 'false', 0, True):
            with self.subTest(value=value):
                self.assertTrue(VERIFIER.validate_build_gate({
                    'build_habilitado': value,
                }))


if __name__ == '__main__':
    unittest.main()
