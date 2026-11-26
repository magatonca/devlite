"""Read-only checks for the future isolated v7 ISO build."""
import json
import subprocess

from v6.storage import require_space
from v7.storage import ROOT, budgets
from v7.admin_bootstrap import ADMIN, CAP, SOURCE_SHA, SOURCE_SIZE


def main():
    try:
        from v7.release_gate import inputs
        needed = budgets(SOURCE_SIZE)['iso']
        print(json.dumps({'source_sha256': SOURCE_SHA, 'iso_budget_bytes': needed,
                          'free_bytes': require_space(ROOT, needed),
                          'administrative_staging_max_bytes': SOURCE_SIZE + CAP}), flush=True)
        if not (ADMIN / 'bootstrap.py').is_file():
            raise ValueError('Bootstrap administrativo ausente. Consulte docs/v7/instalador-local.md.')
        if ROOT.stat().st_dev != ADMIN.stat().st_dev:
            raise ValueError('O staging administrativo e o projeto devem compartilhar o volume monitorado.')
        worker = subprocess.run(['/usr/bin/python3', '-ISB', str(ADMIN / 'bootstrap.py'), '--check'],
                                check=True, capture_output=True, text=True, timeout=180).stdout.strip()
        inputs(worker)
    except subprocess.CalledProcessError as error:
        raise SystemExit(f'Pré-voo bloqueado: {error.stderr.strip()}') from None
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        raise SystemExit(f'Pré-voo bloqueado: {error}') from None


if __name__ == '__main__':
    main()
