"""Conservative storage preflight for v7 development and packaging."""
from v6.storage import GIB, RESERVE, ROOT, stage_budgets

V6_ISO = ROOT / 'artifacts/devlite-v6-6_np5ota/devlite-os-1.0-v6-amd64.iso'
FRONTEND = {
    'flutter archive and SDK': 3 * GIB,
    'build dependencies and sysroot': 4 * GIB,
    'pub, submodule and compiler caches': 5 * GIB,
    'frontend build and retained bundle': 4 * GIB,
}
SNAP = {'build, stage, prime and snap output': 10 * GIB}
ISO_EXTRA = 2 * GIB


def budgets(source_bytes):
    return {
        'frontend': sum(FRONTEND.values()),
        'snap': sum(SNAP.values()),
        'iso': sum(stage_budgets(source_bytes).values()) + ISO_EXTRA,
    }


if __name__ == '__main__':
    from shutil import disk_usage
    import json
    stages = budgets(V6_ISO.stat().st_size)
    free = disk_usage(ROOT).free
    required = sum(stages.values()) + RESERVE
    print(json.dumps({'stages_bytes': stages, 'free_bytes': free, 'reserve_bytes': RESERVE,
                      'required_bytes': required, 'shortfall_bytes': max(0, required - free)}, indent=2))
    if free < required:
        raise SystemExit(1)
