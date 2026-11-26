#!/usr/bin/env python3
"""Valida registros públicos; não cria VM e não executa testes no guest."""
import argparse,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pipeline.devlite.public_acceptance import template,validate
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--template',type=Path);p.add_argument('--report',type=Path);p.add_argument('--iso-sha256');p.add_argument('--evidence-root',type=Path);a=p.parse_args()
 if a.template:
  with a.template.open('x') as stream:json.dump(template(),stream,ensure_ascii=False,indent=2);stream.write('\n')
 elif a.report and a.iso_sha256 and a.evidence_root:
  errors=validate(json.loads(a.report.read_text()),a.iso_sha256,a.evidence_root)
  for error in errors:print('PENDENTE:',error)
  if errors:raise SystemExit(1)
  print('Registros íntegros; conteúdo das evidências ainda exige revisão humana.')
 else:p.error('Informar --template ou --report/--iso-sha256/--evidence-root')
