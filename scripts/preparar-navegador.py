#!/usr/bin/env python3
"""Resolve dependências e exporta configurações de navegador, offline e sem root."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.devlite.browser import prepare
if __name__ == '__main__':
    try:
        print(prepare(ROOT))
    except (OSError, ValueError) as error:
        raise SystemExit(str(error))
