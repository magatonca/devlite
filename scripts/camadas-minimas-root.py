#!/usr/bin/env python3
"""Auxiliar restrito; executar como root somente após confirmação explícita."""
import argparse
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.devlite.minimal_root import main
from pipeline.devlite.runtime import BuildError

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('stage', choices=('extract', 'apply', 'pack'))
    args = parser.parse_args()
    try:
        main(args.workspace, args.stage)
    except (BuildError, OSError, ValueError) as error:
        raise SystemExit(str(error))
