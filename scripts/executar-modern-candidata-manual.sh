#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=/home/magaton/DevLite-OS
EXPECTED_HOST=magaton
EXPECTED_ISO_SHA256=7373cb9be11ebda5218f20795fec87eab20c2cebef3c763ae6e5c63d4e7cd7bd
JOB=${1:?Uso: executar-modern-candidata-manual.sh JOB APPROVAL_SHA256}
APPROVAL=${2:?Uso: executar-modern-candidata-manual.sh JOB APPROVAL_SHA256}

if [[ $(hostname) != "$EXPECTED_HOST" ]]; then
    printf 'Host inesperado: %s\n' "$(hostname)" >&2
    exit 1
fi
if [[ $(id -un) != magaton || $(id -u) -eq 0 ]]; then
    echo 'Execute como o usuário magaton, nunca como root.' >&2
    exit 1
fi
cd "$ROOT"
if [[ -L $JOB || $(realpath -e -- "$JOB") != "$ROOT"/work/modern-candidate-pack-* ]]; then
    echo 'Job fora do workspace autorizado ou symlink.' >&2
    exit 1
fi

JOB=$(realpath -e -- "$JOB")
UNIT="devlite-$(basename -- "$JOB").service"
LOGDIR="$ROOT/work/modern-candidate-manual-$(date -u +%Y%m%dT%H%M%SZ)"
umask 077
mkdir -- "$LOGDIR"
LOG="$LOGDIR/runner.log"
exec > >(tee -a "$LOG") 2>&1
echo "Início UTC: $(date -u +%FT%TZ)"
echo "Host/usuário: $(hostname)/$(id -un)"
echo "Job: $JOB"
echo "Contrato: $APPROVAL"

if systemctl is-active --quiet "$UNIT"; then
    echo "Worker já ativo: $UNIT" >&2
    exit 1
else
    STATE=$?
    if (( STATE != 3 && STATE != 4 )); then
        echo "Não foi possível provar que o worker está inativo (systemctl=$STATE)." >&2
        exit 1
    fi
fi
for pending in execution.lock pack-report.json layers-ready.json; do
    if [[ -e $JOB/$pending || -L $JOB/$pending ]]; then
        echo "Job já tem marcador/recibo ($pending); não será repetido." >&2
        exit 1
    fi
done

python3 - "$JOB" "$APPROVAL" <<'PY'
import shutil
import sys
from pathlib import Path
from pipeline.devlite.modern_candidate import read_job

job, contract, _ = read_job(sys.argv[1], sys.argv[2])
free = shutil.disk_usage(job).free
required = max(70 * 1024**3, contract['initial_required_bytes'])
print(f'Espaço livre: {free} bytes; mínimo selado: {required} bytes')
if free < required:
    raise SystemExit('Espaço livre insuficiente')
if Path(job / 'attempt').exists():
    raise SystemExit('Tentativa anterior encontrada; execução bloqueada')
PY

ISO="$ROOT/artifacts/modern-release-vz4edu99/devlite-os-1.0-amd64.iso"
ACTUAL_ISO_SHA256=$(sha256sum -- "$ISO" | awk '{print $1}')
if [[ $ACTUAL_ISO_SHA256 != "$EXPECTED_ISO_SHA256" ]]; then
    echo "ISO aprovada divergente: $ACTUAL_ISO_SHA256" >&2
    exit 1
fi
echo "ISO aprovada preservada: $ACTUAL_ISO_SHA256"

echo 'Autenticação sudo solicitada pelo mecanismo normal do sistema.'
sudo -v
set +e
python3 scripts/empacotar-modern-candidata.py \
    --job "$JOB" --approval-sha256 "$APPROVAL" --execute-authorized
STATUS=$?
set -e
if (( STATUS != 0 )); then
    echo "Empacotador terminou com código $STATUS; verifique os logs do job."
    exit "$STATUS"
fi

python3 - "$JOB" "$APPROVAL" <<'PY'
import json
import sys
from pathlib import Path

job = Path(sys.argv[1])
approval = sys.argv[2]
report = json.loads((job / 'pack-report.json').read_text())
receipt = json.loads((job / 'layers-ready.json').read_text())
if report.get('status') != 'layers_verified' or report.get('cleanup_errors') != []:
    raise SystemExit('Relatório final do worker não aprovado')
if receipt.get('job_sha256') != approval or receipt.get('iso_generated') is not False:
    raise SystemExit('Receipt de camadas divergente ou fora do escopo')
print('Camadas verificadas:', job / 'layers-ready.json')
print('Relatório:', job / 'pack-report.json')
PY

echo "Fim UTC: $(date -u +%FT%TZ)"
echo "Log manual: $LOG"
