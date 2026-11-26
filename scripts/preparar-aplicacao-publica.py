#!/usr/bin/env python3
"""Prepare a sealed application/integration job as magaton; no mounts or execution."""
import argparse,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pipeline.devlite.public_execution import prepare
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--payload-job',type=Path,required=True);p.add_argument('--diagnostic-only',action='store_true');a=p.parse_args()
 try:
  job,approval=prepare(a.payload_job,a.diagnostic_only);print(job);print(approval)
 except (OSError,ValueError) as error:raise SystemExit(str(error))
