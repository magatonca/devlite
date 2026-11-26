#!/usr/bin/env python3
"""Exporta protótipos; nunca aplica configurações no host ou nas imagens."""
import sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pipeline.devlite.modern_preview import prepare
if __name__=='__main__':
    try: print(prepare(ROOT))
    except (OSError,ValueError) as error: raise SystemExit(str(error))
