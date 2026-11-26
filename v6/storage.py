"""Storage preflight for the incremental v6 build."""
import argparse
import json
import shutil
import os
import signal
import subprocess
from pathlib import Path

GIB = 1024**3
RESERVE = 10 * GIB
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts/devlite-v5-ld_eufxi/devlite-os-1.0-v5-amd64.iso"


def stage_budgets(source_bytes):
    """Incremental caps including outputs retained by each stage."""
    return {
        "pack": 8 * GIB,
        "assemble": 2 * source_bytes + 2 * GIB,
        "verify": source_bytes + GIB,
    }


def require_space(path, growth_bytes, disk_usage=shutil.disk_usage):
    if growth_bytes < 0:
        raise ValueError("A estimativa de crescimento deve ser positiva ou zero.")
    free = disk_usage(path).free
    if free < RESERVE + growth_bytes:
        raise ValueError(
            f"Espaço insuficiente: {free} bytes livres, "
            f"{RESERVE + growth_bytes} necessários com a reserva."
        )
    return free


def run_stage(command, growth_bytes):
    """Run an unprivileged stage with its outputs on the project filesystem."""
    require_space(ROOT, growth_bytes)
    if os.geteuid() == 0:
        raise ValueError("Execute a etapa como usuário sem privilégios.")
    buffer = 512 * 1024**2
    with subprocess.Popen(command, cwd=ROOT, start_new_session=True) as process:
        try:
            while True:
                try:
                    return process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    require_space(ROOT, buffer)
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("all", "pack", "assemble", "verify"))
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command[:1] == ["--"]:
        command = command[1:]
    if command and args.stage == "all":
        parser.error("Informe uma etapa específica para executar um comando.")
    budgets = stage_budgets(SOURCE.stat().st_size)
    growth = sum(budgets.values()) if args.stage == "all" else budgets[args.stage]
    try:
        free = require_space(ROOT, growth)
        print(json.dumps({"stage": args.stage, "free_bytes": free,
                          "growth_budget_bytes": growth, "reserve_bytes": RESERVE}), flush=True)
        if command:
            raise SystemExit(run_stage(command, growth))
    except (ValueError, OSError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
