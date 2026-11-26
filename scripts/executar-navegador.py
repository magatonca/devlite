#!/usr/bin/env python3
"""Prepare browser contract without root; privileged modes require separate approval."""
import argparse,signal,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pipeline.devlite.browser_executor import prepare,outer,inner,view_worker

def interrupted(number,frame):raise RuntimeError('Browser operation interrupted: '+str(number))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    modes=p.add_mutually_exclusive_group(required=True)
    modes.add_argument('--prepare',type=Path);modes.add_argument('--outer',action='store_true')
    modes.add_argument('--inner',action='store_true');modes.add_argument('--view',choices=('base','live'))
    p.add_argument('--job',type=Path);p.add_argument('--approval-sha256');p.add_argument('--execute-authorized',action='store_true')
    p.add_argument('--external-evidence-fd',type=int);p.add_argument('--external-evidence-sha256');p.add_argument('--execution-nonce')
    a=p.parse_args()
    signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGHUP,interrupted)
    try:
        if a.prepare:
            if a.execute_authorized:raise ValueError('Preparation must not authorize execution')
            job,approval=prepare(a.prepare);print(job);print(approval)
        elif not a.job or not a.approval_sha256 or not a.execute_authorized:raise ValueError('Explicit job/hash/approval required')
        elif a.outer:print(outer(a.job,a.approval_sha256,True))
        elif a.inner:print(inner(a.job,a.approval_sha256,True,external={'fd':a.external_evidence_fd,'sha256':a.external_evidence_sha256,'nonce':a.execution_nonce}))
        else:view_worker(a.job,a.view,a.approval_sha256)
    except (OSError,ValueError,RuntimeError) as error:raise SystemExit(str(error))
