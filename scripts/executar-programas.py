#!/usr/bin/env python3
"""Prepara/revisa o executor. --execute/--recover exigem autorização separada."""
import argparse
import json
import signal
import sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pipeline.devlite.customize.executor_contract import prepare
from pipeline.devlite.customize.executor import execute,recover
from pipeline.devlite.customize.manifest import SpecError
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare',type=Path,metavar='PLANO_4B2')
    mode.add_argument('--probe',action='store_true');mode.add_argument('--execute',action='store_true');mode.add_argument('--recover',action='store_true')
    parser.add_argument('--job',type=Path);parser.add_argument('--approval-sha256')
    args=parser.parse_args()
    def interrupted(signum,frame): raise InterruptedError('Executor interrompido por sinal '+str(signum))
    if args.execute or args.probe:
        signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGHUP,interrupted)
    try:
        if args.prepare: print(prepare(args.prepare))
        elif not args.job or not args.approval_sha256: parser.error('--job e --approval-sha256 obrigatórios')
        elif args.probe: print(execute(args.job,args.approval_sha256,probe=True))
        elif args.execute: print(execute(args.job,args.approval_sha256))
        else: recover(args.job,args.approval_sha256)
    except (SpecError,OSError,ValueError) as error: raise SystemExit(str(error))
