#!/usr/bin/env python3
"""Verify the sealed namespace handoff before starting the root worker."""
import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.devlite.modern_candidate import read_job

WORKER_ENV = {
    'PATH': '/usr/sbin:/usr/bin:/sbin:/bin',
    'LC_ALL': 'C',
    'TZ': 'UTC',
    'PYTHONDONTWRITEBYTECODE': '1',
    'PYTHONPATH': str(ROOT),
}


def load_packager():
    spec = importlib.util.spec_from_file_location(
        'modern_candidate_packager', ROOT / 'scripts/empacotar-modern-candidata.py'
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--job', type=Path, required=True)
    parser.add_argument('--approval-sha256', required=True)
    parser.add_argument('--execute-authorized', action='store_true')
    parser.add_argument('namespace_args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if os.geteuid() != 0 or not args.execute_authorized:
        raise ValueError('Entrada root isolada requer autorização explícita')
    job, contract, _ = read_job(args.job, args.approval_sha256, root=True)
    namespace = args.namespace_args[1:] if args.namespace_args[:1] == ['--'] else args.namespace_args
    if namespace != load_packager().namespace_command(job, args.approval_sha256):
        raise ValueError('Comando de namespace difere do contrato selado')
    return subprocess.call(
        namespace, stdin=subprocess.DEVNULL, close_fds=True,
        cwd=ROOT, env=WORKER_ENV,
    )


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit(str(error))
