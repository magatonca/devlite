#!/usr/bin/env python3
"""Audita banco dpkg extraído ou arquivos deb locais; nunca instala."""
import argparse
import json
import sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pipeline.devlite.customize.installation import audit_database,verify_archives
from pipeline.devlite.customize.manifest import SpecError

def confined(path):
    original=path.absolute()
    if original.is_symlink() or not original.resolve().is_relative_to((ROOT/'work').resolve()):
        raise SpecError('A auditoria exige cópias dentro de work')
    return original.resolve()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rootfs',type=Path)
    parser.add_argument('--plan',type=Path)
    parser.add_argument('--debs',type=Path)
    args=parser.parse_args()
    try:
        if args.rootfs and not (args.plan or args.debs):
            print(json.dumps(audit_database(confined(args.rootfs)),indent=2))
        elif args.plan and args.debs and not args.rootfs:
            plan=json.loads(confined(args.plan).read_text())
            print('Debs conferidos:',verify_archives(plan,confined(args.debs)))
        else: parser.error('Use --rootfs ou --plan com --debs')
    except (SpecError,OSError,ValueError) as error: raise SystemExit(str(error))
