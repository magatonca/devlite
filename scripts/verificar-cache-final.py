#!/usr/bin/env python3
"""Verifica somente cache já adquirido após autorização; nunca baixa ou instala."""
import argparse,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pipeline.devlite.final_artifacts import verify
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cache',type=Path,required=True);a=p.parse_args()
 try:print(json.dumps(verify(json.loads((ROOT/'packages/final-external-plan.json').read_text()),a.cache),ensure_ascii=False,indent=2))
 except (ValueError,OSError) as error:raise SystemExit(str(error))
