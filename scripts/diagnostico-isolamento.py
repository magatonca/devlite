#!/usr/bin/env python3
"""Lê estado de isolamento do host; imprime JSON, sem elevar privilégios."""
import json
import os
import sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pipeline.devlite.customize.isolation_validation import collect
if __name__=='__main__':
    if os.geteuid()==0: raise SystemExit('Executar como magaton, sem sudo')
    print(json.dumps(collect(ROOT),ensure_ascii=False,indent=2))
