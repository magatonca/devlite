#!/usr/bin/env python3
"""Verifica estrutura e bloqueios da Fase 1, sem modificar arquivos."""
import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    required = ['README.md', 'CONTRIBUTING.md', '.gitignore', '.gitattributes',
                'config/projeto.json', 'scripts/diagnostico.py', 'tests/aceitacao.md']
    required += ['docs/' + name + '.md' for name in
                 ('arquitetura', 'plano', 'seguranca-validacao', 'recursos', 'iso-base', 'decisoes')]
    required += [name + '/README.md' for name in ('packages', 'overlay', 'assets', 'pipeline')]
    required += [name + '/.gitkeep' for name in ('sources', 'work', 'artifacts', 'reports')]
    errors = [f'Ausente: {name}' for name in required if not (root / name).is_file()]
    try:
        config = json.loads((root / 'config/projeto.json').read_text())
        for key in ('build_habilitado', 'downloads_autorizados'):
            if config.get(key) is not False:
                errors.append(f'{key} deve ser false')
        if config.get('fase') != 1:
            errors.append('Fase deve ser 1')
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
    for error in errors:
        print('ERRO:', error)
    print(f'Verificação da Fase 1: {len(errors)} erro(s).')
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
