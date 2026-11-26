#!/usr/bin/env python3
"""Fluxo integrado: prepara e valida sem executar operações privilegiadas automaticamente."""
import argparse
import json
import sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pipeline.devlite.release_flow import prepare
from pipeline.devlite.release_iso import build,reproduce
from pipeline.devlite.release_acceptance import validate
from pipeline.devlite.customize.manifest import SpecError
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);m=p.add_mutually_exclusive_group(required=True)
 m.add_argument('--prepare',action='store_true');m.add_argument('--build-iso',type=Path);m.add_argument('--verify-reproducibility',type=Path);m.add_argument('--validate-acceptance',type=Path)
 p.add_argument('--reference-report',type=Path);p.add_argument('--approval-sha256');p.add_argument('--iso-sha256');p.add_argument('--evidence-root',type=Path);a=p.parse_args()
 try:
  if a.prepare:print(prepare())
  elif a.verify_reproducibility:
   if not a.approval_sha256 or not a.reference_report:p.error('--approval-sha256 e --reference-report obrigatórios')
   print(reproduce(a.verify_reproducibility,a.approval_sha256,a.reference_report))
  elif a.build_iso:
   if not a.approval_sha256:p.error('--approval-sha256 obrigatório')
   print(build(a.build_iso,a.approval_sha256))
  else:
   if not a.iso_sha256 or not a.evidence_root:p.error('--iso-sha256 e --evidence-root obrigatórios')
   errors=validate(json.loads(a.validate_acceptance.read_text()),a.iso_sha256,a.evidence_root)
   for error in errors:print('PENDENTE:',error)
   if errors:raise SystemExit(1)
   print('Evidências documentais íntegras; aprovação humana do conteúdo continua necessária.')
 except (SpecError,OSError,ValueError) as error:raise SystemExit(str(error))
