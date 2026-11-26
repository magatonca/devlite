#!/usr/bin/env python3
"""Prepara manifesto ou baixa debs após autorização específica. Nunca instala."""
import argparse
import sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pipeline.devlite.customize.package_acquisition import prepare,download
from pipeline.devlite.customize.manifest import SpecError
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--prepare',type=Path);modes.add_argument('--download',type=Path)
    parser.add_argument('--approval-sha256')
    args=parser.parse_args()
    try:
        if args.prepare:print(prepare(args.prepare))
        elif not args.approval_sha256:parser.error('--approval-sha256 obrigatório para download')
        else:print(download(args.download,args.approval_sha256))
    except (SpecError,OSError,ValueError) as error:raise SystemExit(str(error))
