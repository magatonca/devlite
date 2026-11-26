#!/usr/bin/env python3
"""Reconstrução sem customizações; nenhuma VM é iniciada e nada é apagado."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.devlite.build import build, preflight, reproduce
from pipeline.devlite.runtime import BuildError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--build', action='store_true', help='executar reconstrução experimental autorizada')
    modes.add_argument('--verify-reproducibility', type=Path, metavar='BUILD_REPORT', help='gerar novamente e comparar com artefato validado')
    args = parser.parse_args()
    try:
        if args.verify_reproducibility:
            reproduce(ROOT, args.verify_reproducibility)
        elif args.build:
            build(ROOT)
        else:
            source = preflight(ROOT)
            print(f'Preflight OK: {source}. Use --build para construir. Nenhuma saída criada.')
    except (BuildError, OSError, ValueError) as error:
        print(f'ERRO: {error}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
