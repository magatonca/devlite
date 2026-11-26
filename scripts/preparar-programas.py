#!/usr/bin/env python3
"""Prepara resolução APT offline. Não possui modo de instalação ou build."""
import argparse
import json
import sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pipeline.devlite.customize.installation import prepare
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resolve-offline',action='store_true',help='copia índices Ubuntu locais e simula contra dpkg da imagem')
    args=parser.parse_args()
    if not args.resolve_offline:
        print('Use --resolve-offline como magaton. Não há instalação, update, download ou build.')
    else:
        report=prepare(ROOT)
        print(json.dumps({k:report[k] for k in ('status','ready_to_install','blockers')},ensure_ascii=False,indent=2))
        raise SystemExit(1 if report['status']=='bloqueado' else 0)
