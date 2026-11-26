#!/usr/bin/env python3
"""Integração futura de camadas; exige root e namespace aprovados. Não gera ISO."""
import argparse
import signal
import sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pipeline.devlite.release_pack import run
from pipeline.devlite.customize.manifest import SpecError
def interrupted(signum,frame):
 raise SpecError('Integração interrompida pelo sinal '+str(signum))

if __name__=='__main__':
 signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGHUP,interrupted)
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--job',type=Path,required=True);p.add_argument('--approval-sha256',required=True);a=p.parse_args()
 try:print(run(a.job,a.approval_sha256))
 except (SpecError,OSError,ValueError) as error:raise SystemExit(str(error))
