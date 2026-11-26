#!/usr/bin/env python3
"""Stage authenticated public files as magaton; no downloads or image changes."""
import argparse,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pipeline.devlite.final_payload import stage
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cache',type=Path,required=True);p.add_argument('--stage',action='store_true',required=True);a=p.parse_args()
 try:
  plan=json.loads((ROOT/'packages/final-external-plan.json').read_text());branding=json.loads((ROOT/'config/final-branding-plan.json').read_text())
  print(stage(ROOT,a.cache,plan,branding))
 except (OSError,ValueError) as error:raise SystemExit(str(error))
