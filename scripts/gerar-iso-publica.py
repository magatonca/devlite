#!/usr/bin/env python3
"""Prepare or generate exactly one public candidate; no sudo, mounts or packages."""
import argparse,signal,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pipeline.devlite.public_iso_control import prepare,run
def stop(signum,frame):raise RuntimeError('Geração interrompida: '+str(signum))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',type=Path);p.add_argument('--application-sha256')
 p.add_argument('--job',type=Path);p.add_argument('--approval-sha256');p.add_argument('--execute-authorized',action='store_true');a=p.parse_args()
 signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGHUP,stop)
 try:
  if a.prepare and a.application_sha256 and not a.execute_authorized:
   job,sha=prepare(a.prepare,a.application_sha256);print(job);print(sha)
  elif a.job and a.approval_sha256 and a.execute_authorized:print(run(a.job,a.approval_sha256,True))
  else:p.error('Informar --prepare/--application-sha256 ou --job/--approval-sha256/--execute-authorized')
 except (OSError,ValueError,RuntimeError) as error:raise SystemExit(str(error))
