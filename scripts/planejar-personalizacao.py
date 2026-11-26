#!/usr/bin/env python3
"""Valida e exporta um plano de personalização; não aplica nem instala nada."""
import argparse
import json
import pwd
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.devlite.customize.planner import make_plan, export_plan
from pipeline.devlite.customize.layers import audit
from pipeline.devlite.customize.integrity import verify_export
from pipeline.devlite.runtime import BuildError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-apt-cache', action='store_true', help='consultar somente os índices locais')
    parser.add_argument('--audit-layers', action='store_true', help='ler listagens da inspeção da Fase 2')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--export', action='store_true', help='exportar overlay e plano em novo diretório work/phase4a-*')
    modes.add_argument('--verify-export', type=Path, help='conferir integridade de um overlay já preparado em work')
    args = parser.parse_args()
    try:
        if args.verify_export:
            if args.check_apt_cache or args.audit_layers:
                parser.error('--verify-export não combina com auditoria/cache')
            directory = args.verify_export
            if directory.is_symlink() or not directory.resolve().is_relative_to((ROOT / 'work').resolve()):
                raise ValueError('Verificar apenas diretório preparado dentro de work')
            print(json.dumps(verify_export(directory), ensure_ascii=False, indent=2))
            return 0
        if args.export and pwd.getpwuid(os.getuid()).pw_name != 'magaton':
            raise ValueError('Exportar como magaton; não usar sudo')
        result = None
        if args.audit_layers:
            directory = ROOT / 'reports/phase2'
            result = audit((directory / 'minimal.squashfs-files.txt').read_text(),
                           (directory / 'minimal.live.squashfs-files.txt').read_text())
        plan = make_plan(ROOT, args.check_apt_cache, result)
        if args.export:
            print(export_plan(ROOT, plan))
        else:
            print(json.dumps(plan, ensure_ascii=False, indent=2))
    except (OSError, ValueError, BuildError) as error:
        print(f'ERRO: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
