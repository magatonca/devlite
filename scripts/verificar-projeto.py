#!/usr/bin/env python3
"""Verifica estrutura e bloqueios da fase atual, sem modificar arquivos."""
import json
from pathlib import Path


def validate_build_gate(config):
    if config.get('build_habilitado') is not False:
        return ['build_habilitado deve ser false; builds exigem aprovação operacional separada']
    return []


def main():
    root = Path(__file__).resolve().parents[1]
    required = ['README.md', 'CONTRIBUTING.md', '.gitignore', '.gitattributes',
                'config/projeto.json', 'scripts/diagnostico.py', 'tests/aceitacao.md']
    required += ['docs/' + name + '.md' for name in
                 ('arquitetura', 'plano', 'seguranca-validacao', 'recursos', 'iso-base', 'decisoes')]
    required += [name + '/README.md' for name in ('packages', 'overlay', 'assets', 'pipeline')]
    required += [name + '/.gitkeep' for name in ('sources', 'work', 'artifacts', 'reports')]
    errors = [f'Ausente: {name}' for name in required if not (root / name).is_file()]
    try:
        config = json.loads((root / 'config/projeto.json').read_text())
        errors.extend(validate_build_gate(config))
        if config.get('fase') not in (1, 2, 3, 4):
            errors.append('Fase deve ser 1, 2, 3 ou 4A')
        if config.get('fase') == 1 and config.get('downloads_autorizados') is not False:
            errors.append('Downloads não autorizados na Fase 1')
        if config.get('fase') == 2:
            if config.get('downloads_autorizados') is not True or not config.get('autorizacao_download'):
                errors.append('Fase 2 requer registro da autorização de aquisição')
            for name in ('scripts/validar-iso.py', 'scripts/inspecionar-iso.py', 'tests/test_validar_iso.py'):
                if not (root / name).is_file():
                    errors.append(f'Ausente: {name}')
        if config.get('fase') == 3:
            if config.get('subfase') not in ('A', 'B'):
                errors.append('Subfase deve ser A ou B')
            for field in ('downloads_autorizados', 'criacao_vms_autorizada', 'instalacao_xubuntu_autorizada'):
                if config.get(field) is not False:
                    errors.append(f'{field} deve ser false na preparação 3A')
            for name in ('scripts/validar-iso.py', 'scripts/inspecionar-iso.py',
                         'scripts/diagnostico-virtualizacao.py', 'scripts/validar-relatorio-iso.py',
                         'docs/fase3a-testes-iso.md', 'tests/test_fase3a.py', 'tests/modelo-relatorio-iso.json'):
                if not (root / name).is_file():
                    errors.append(f'Ausente: {name}')
            if config.get('subfase') == 'B':
                for name in ('scripts/construir-iso.py', 'pipeline/devlite/build.py', 'tests/test_pipeline.py', 'docs/fase3b-pipeline.md'):
                    if not (root / name).is_file():
                        errors.append(f'Ausente: {name}')
        if config.get('fase') == 4:
            if config.get('subfase') not in ('A', 'B.1', 'B.2', 'B.3', 'B.4', 'B.5', 'B.7-9'):
                errors.append('Subfase 4 deve ser A, B.1, B.2, B.3, B.4, B.5 ou B.7-9')
            for field in ('repositorios_externos_autorizados', 'downloads_autorizados'):
                if config.get(field) is not False:
                    errors.append(f'{field} deve permanecer false')
            if config.get('subfase') in ('A', 'B.2', 'B.3', 'B.4', 'B.5', 'B.7-9'):
                for field in ('personalizacao_habilitada', 'operacoes_privilegiadas_autorizadas'):
                    if config.get(field) is not False:
                        errors.append(f'{field} deve ser false na preparação 4A/4B.2')
            else:
                if config.get('personalizacao_habilitada') is not True or config.get('pacotes_na_imagem_habilitados') is not False:
                    errors.append('4B.1 permite somente configurações, sem pacotes')
                for name in ('scripts/personalizar-minima.py', 'scripts/camadas-minimas-root.py',
                             'pipeline/devlite/minimal_build.py', 'pipeline/devlite/minimal_root.py',
                             'pipeline/devlite/minimal_config.py', 'tests/test_minimal_customization.py',
                             'docs/fase4b1-personalizacao-minima.md'):
                    if not (root / name).is_file():
                        errors.append(f'Ausente: {name}')
            if config.get('subfase') in ('B.2', 'B.3', 'B.4', 'B.5', 'B.7-9'):
                if config.get('pacotes_na_imagem_habilitados') is not False:
                    errors.append('4B.2 não autoriza instalação de pacotes')
                for name in ('scripts/preparar-programas.py', 'scripts/auditar-programas.py',
                             'pipeline/devlite/customize/installation.py', 'pipeline/devlite/customize/service_profiles.py',
                             'tests/test_installation_plan.py', 'docs/fase4b2-preparacao-programas.md'):
                    if not (root / name).is_file():
                        errors.append(f'Ausente: {name}')
            if config.get('subfase') in ('B.3', 'B.4', 'B.5', 'B.7-9'):
                if any(config.get(field) is not False for field in ('executor_autorizado','probe_autorizado','recuperacao_autorizada')):
                    errors.append('Executor não autorizado na preparação 4B.3')
                for name in ('scripts/executar-programas.py', 'pipeline/devlite/customize/executor.py',
                             'pipeline/devlite/customize/executor_contract.py', 'pipeline/devlite/customize/executor_worker.py',
                             'pipeline/devlite/customize/guest_runner.py', 'tests/test_executor.py',
                             'docs/fase4b3-executor-isolado.md'):
                    if not (root / name).is_file(): errors.append(f'Ausente: {name}')
            if config.get('subfase') in ('B.4', 'B.5', 'B.7-9'):
                for name in ('scripts/diagnostico-isolamento.py', 'pipeline/devlite/customize/isolation_validation.py',
                             'tests/test_isolation_validation.py', 'docs/fase4b4-validacao-isolamento.md'):
                    if not (root / name).is_file(): errors.append(f'Ausente: {name}')
            if config.get('subfase') in ('B.5', 'B.7-9'):
                if config.get('download_pacotes_autorizado') is not False:
                    errors.append('Download de pacotes não autorizado na preparação 4B.5')
                for name in ('scripts/pacotes-controlados.py', 'pipeline/devlite/customize/package_acquisition.py',
                             'tests/test_package_acquisition.py', 'docs/fase4b5-preparacao-pacotes.md'):
                    if not (root / name).is_file(): errors.append(f'Ausente: {name}')
            if config.get('subfase') == 'B.7-9':
                if any(config.get(field) is not False for field in ('integracao_camadas_autorizada','iso_final_autorizada')):
                    errors.append('Integração e geração ISO permanecem desabilitadas nesta preparação')
                for name in ('scripts/devlite-release.py','scripts/integrar-release-root.py','scripts/instalar-release-root.py','pipeline/devlite/release_install.py',
                             'pipeline/devlite/release_flow.py','pipeline/devlite/release_layers.py',
                             'pipeline/devlite/release_pack.py','pipeline/devlite/release_iso.py',
                             'pipeline/devlite/release_acceptance.py','pipeline/devlite/release_contract.py',
                             'tests/test_release_pipeline.py','docs/fases4b7-9-integradas.md'):
                    if not (root / name).is_file():errors.append(f'Ausente: {name}')
            for name in ('packages/selection.json', 'packages/sources.json', 'config/customization.json',
                         'config/customization-lock.json', 'scripts/planejar-personalizacao.py',
                         'pipeline/devlite/customize/planner.py', 'tests/test_customization.py',
                         'docs/fase4a-personalizacao.md', 'docs/pacotes-origens.md'):
                if not (root / name).is_file():
                    errors.append(f'Ausente: {name}')
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
    for error in errors:
        print('ERRO:', error)
    print(f'Verificação do projeto: {len(errors)} erro(s).')
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
