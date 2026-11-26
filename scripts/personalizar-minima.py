#!/usr/bin/env python3
"""Prepara configurações ou monta ISO após as três etapas root confirmadas."""
import argparse
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.devlite.minimal_build import prepare, assemble
from pipeline.devlite.build import preflight
from pipeline.devlite.runtime import BuildError

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--prepare', action='store_true')
    modes.add_argument('--assemble', type=Path, metavar='WORKSPACE')
    args = parser.parse_args()
    try:
        if args.prepare:
            prepare(ROOT)
        elif args.assemble:
            assemble(ROOT, args.assemble.resolve())
        else:
            preflight(ROOT)
            print('Preflight OK. --prepare não usa root; operações root exigem confirmação separada.')
    except (BuildError, OSError, ValueError) as error:
        raise SystemExit(str(error))
