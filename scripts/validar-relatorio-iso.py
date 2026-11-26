#!/usr/bin/env python3
"""Valida evidências manuais; não executa testes de boot ou instalação."""
import argparse
import json
from pathlib import Path

ISO = 'xubuntu-24.04.5-minimal-amd64.iso'
SHA256 = '9d47f975696ce496b8be882b6d7cc9079c1ea89fb625ac2c86caa63a4f180033'
CHECKS = ('isolamento_disco', 'hash_iso', 'boot_live', 'firmware_live',
          'xfce_live', 'teclado_live', 'instalador', 'instalacao',
          'boot_sem_iso', 'firmware_instalado', 'xfce_instalado',
          'locale_instalado', 'persistencia_reboot', 'desligamento')
ENVIRONMENT = ('data', 'operador', 'versao_workstation', 'windows', 'vm',
               'cpu', 'ram', 'disco_virtual', 'rede', 'secure_boot',
               'modo_instalacao', 'atualizacao_instalador', 'idioma_live')


def validate(report):
    errors = []
    if not isinstance(report, dict):
        return ['Relatório deve ser objeto JSON.']
    if report.get('iso') != ISO or report.get('sha256') != SHA256:
        errors.append('ISO ou SHA-256 difere da base autenticada.')
    runs = report.get('execucoes')
    if not isinstance(runs, dict) or set(runs) != {'bios', 'uefi'}:
        return errors + ['Necessárias execuções independentes bios e uefi.']
    vm_ids = []
    for firmware in ('bios', 'uefi'):
        run = runs[firmware]
        if not isinstance(run, dict):
            errors.append(f'{firmware}: execução inválida.')
            continue
        environment = run.get('ambiente', {})
        if not isinstance(environment, dict):
            errors.append(f'{firmware}: ambiente inválido.')
            environment = {}
        for field in ENVIRONMENT:
            if not isinstance(environment.get(field), str) or not environment[field].strip():
                errors.append(f'{firmware}: ambiente.{field} não preenchido.')
        vm_ids.append(environment.get('vm'))
        checks = run.get('criterios', {})
        if not isinstance(checks, dict):
            errors.append(f'{firmware}: critérios inválidos.')
            checks = {}
        for name in CHECKS:
            check = checks.get(name)
            if not isinstance(check, dict) or check.get('status') != 'aprovado':
                errors.append(f'{firmware}/{name}: não aprovado.')
            elif not isinstance(check.get('evidencia'), str) or not check['evidencia'].strip():
                errors.append(f'{firmware}/{name}: evidência obrigatória.')
    if len(vm_ids) == 2 and vm_ids[0] == vm_ids[1]:
        errors.append('BIOS e UEFI devem identificar VMs independentes.')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('relatorio', type=Path)
    args = parser.parse_args()
    try:
        errors = validate(json.loads(args.relatorio.read_text()))
    except (OSError, ValueError) as exc:
        errors = [str(exc)]
    if errors:
        for error in errors:
            print('PENDENTE/ERRO:', error)
        return 1
    print('Relatório completo: critérios declarados aprovados para BIOS e UEFI.')
    print('Validação documental; evidências requerem revisão humana. Não autoriza build.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
