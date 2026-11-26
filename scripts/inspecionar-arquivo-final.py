#!/usr/bin/env python3
"""Inspeciona cache externo previamente autenticado, sem extração ou execução."""
import argparse,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pipeline.devlite.final_artifacts import verify
from pipeline.devlite.final_archive import inspect
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cache',type=Path,required=True);p.add_argument('--artifact-id',choices=('node-lts','typescript','@typescript/typescript-linux-x64'),required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 try:
  plan=json.loads((ROOT/'packages/final-external-plan.json').read_text());verify(plan,a.cache);item=next(i for i in plan['artifacts'] if i['id']==a.artifact_id)
  prefix='node-v26.13.1-linux-x64' if a.artifact_id=='node-lts' else 'package';limit=plan['max_unpacked_node_bytes'] if a.artifact_id=='node-lts' else plan['max_unpacked_typescript_bytes']
  result=inspect(a.cache/item['filename'],prefix,limit)
  with a.output.open('x') as stream:json.dump(result,stream,ensure_ascii=False,indent=2);stream.write('\n')
 except (OSError,ValueError) as error:raise SystemExit(str(error))
