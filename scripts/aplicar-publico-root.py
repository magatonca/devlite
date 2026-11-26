#!/usr/bin/env python3
"""Approved public copy/integration worker. No chroot, target programs or ISO."""
import argparse,signal,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pipeline.devlite.public_execution import run
def stop(signum,frame):raise RuntimeError('Public operation interrupted: '+str(signum))
if __name__=='__main__':
 signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGHUP,stop)
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--job',type=Path,required=True);p.add_argument('--approval-sha256',required=True);p.add_argument('--execute-authorized',action='store_true');p.add_argument('--external-evidence-fd',type=int);p.add_argument('--external-evidence-sha256');p.add_argument('--execution-nonce');a=p.parse_args()
 try:print(run(a.job,a.approval_sha256,a.execute_authorized,external={'fd':a.external_evidence_fd,'sha256':a.external_evidence_sha256,'nonce':a.execution_nonce}))
 except (OSError,ValueError,RuntimeError) as error:raise SystemExit(str(error))
