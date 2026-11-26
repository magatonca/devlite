#!/usr/bin/env python3
"""Record effective service isolation, then enter the exact sealed namespace argv."""
import argparse,os,secrets,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pipeline.devlite.public_execution import read,namespace_command
from pipeline.devlite.public_isolation import capture
from pipeline.devlite.public_attestation import seal
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--job',type=Path,required=True);p.add_argument('--approval-sha256',required=True);p.add_argument('--execute-authorized',action='store_true');p.add_argument('namespace_args',nargs=argparse.REMAINDER);a=p.parse_args()
 try:
  if os.geteuid()!=0 or not a.execute_authorized:raise ValueError('Separately approved root entry required')
  job,data=read(a.job,a.approval_sha256)
  args=a.namespace_args[1:] if a.namespace_args[:1]==['--'] else a.namespace_args
  if args!=namespace_command(job,a.approval_sha256):raise ValueError('Namespace command differs from sealed profile')
  report=capture(job,data,'systemd',approval_sha256=a.approval_sha256)
  nonce=secrets.token_hex(32);fd,sha=seal(report,job,a.approval_sha256,nonce)
  try:
   inherited=['--external-evidence-fd',str(fd),'--external-evidence-sha256',sha,'--execution-nonce',nonce]
   result=subprocess.call(args+inherited,stdin=subprocess.DEVNULL,close_fds=True,pass_fds=(fd,))
  finally:os.close(fd)
  raise SystemExit(result)
 except (OSError,ValueError,RuntimeError) as error:raise SystemExit(str(error))
