# Correção pontual do diagnóstico da limpeza

> Execução autorizada concluída: [21 caminhos removidos e 71,12 GiB livres](limpeza-concluida.md). O texto abaixo documenta a revisão anterior à execução; não repetir a limpeza.

**Preparada, não executada.** A lista de 21 caminhos e o manifesto de exclusão permanecem inalterados. Nenhum candidato foi apagado nesta correção.

## Causa e evidência disponível

O relatório original limpeza-controlada-dbaxme6_.json registra PID 112774, 552.420 entradas, 53.558.140.928 bytes alocados e deleted vazio. Não registra nome, referência nem caminho. O PID já não está presente em /proc. Portanto, não há evidência para afirmar falso positivo ou identificar o programa retroativamente.

Hipóteses: leitor temporário ou outra referência legítima a um candidato; não se pode excluir retrospectivamente uma referência do controlador, pois seu PID não foi registrado. As leituras normais de hashes e inventário usam context managers que fecham os arquivos; o código não demonstra que elas tenham deixado uma referência aberta. O próprio controlador continua sujeito ao bloqueio.

## Correção

resources_clear mantém consultas de loops, unidades, mounts de todos os processos e uso de candidatos. Adiciona identidade PID + start_ticks (tempo de início no procfs), nome do processo e reconfirmação da referência antes de declarar uso ativo.

O relatório passa a registrar pid, process_name, start_ticks, path/raw_path, candidate, reference_type (cwd/root/fd), número do descritor, source_path em /proc e is_controller. Mounts registram mount_root/mountpoint. O controlador persiste resource_checks e resource_block antes de sair com erro.

ENOENT/ESRCH decorrentes de término confirmado do processo são registrados como process_disappeared. Descritor fechado ou referência liberada durante a confirmação gera reference_released. Processo vivo com referência ainda em candidato bloqueia. Reutilização de PID, falta de metadados de processo existente e erros de permissão continuam impedindo a limpeza. Nenhum PID é ignorado e não há nova tentativa automática nem encerramento de processos.

Symlinks, hardlinks, filesystem, fontes preservadas e rotina de exclusão não foram modificados. As verificações representam observações durante o preflight, sem congelar processos: uma referência nova pode surgir depois da consulta. O novo preflight privilegiado ainda não foi executado.

## Validação e integridade

**271 testes aprovados**, sendo 20 específicos de limpeza/diagnóstico. Cobertura: referências ativas cwd/root/fd, controlador em uso, término antes/durante inspeção, descritor liberado, PID reutilizado, permissões, metadados incompletos, mounts e persistência do erro estruturado sem chamar exclusão. Os testes usam procfs simulado e arquivos de fixture.

[Saída da suíte](../reports/testes-correcao-diagnostico-limpeza.txt), [evidência e hashes](evidencias/limpeza-correcao-diagnostico.json). Arquivos críticos do host e contrato experimental selado conferidos, sem alterações.

SHA-256 do manifesto de revisão `config/limpeza-diagnostico.sha256`:

```text
3a15d88bb8ead6f5085733dfd8f43e3b4eed617b19055c8ef51c86189de8e620
```

| Arquivo | SHA-256 |
|---|---|
| pipeline/devlite/final_cleanup.py | e0d611fabfd2466a316f695e8f1713f7fd2ba4224b35637aab1fbe4dd6c0cb2d |
| scripts/limpeza-controlada-final.py | 6e28b0c8975726e1e46addf39de028de48fae8a2e92c6bc300a75a43ae4c737f |
| tests/test_final_cleanup.py | 4cfd5ef65a7169d61b9e260b151af1e38a4b90e3a41b4efb9e19a553ddb112af |
| docs/evidencias/plano-limpeza-final.json | c0b96d65c99c175f7ccb0d2869579717dc700a7eb80b5625a66df0c083458c90 |

## Novo comando para a tentativa

**Exige nova autorização; não foi executado.** A mudança está no código e nos hashes; os argumentos e o SHA-256 do plano de 21 caminhos permanecem os mesmos. Esta autorização seria somente para preflight e limpeza delimitada, sem download, instalação ou ISO.

Na raiz do projeto, como magaton, conferir o manifesto. Prosseguir somente se todas as linhas retornarem OK e o próprio manifesto tiver o SHA-256 acima:

```sh
cd /home/magaton/DevLite-OS
sha256sum config/limpeza-diagnostico.sha256
sha256sum --check config/limpeza-diagnostico.sha256
```

Após autorização explícita:

```sh
sudo env PYTHONDONTWRITEBYTECODE=1 python3 /home/magaton/DevLite-OS/scripts/limpeza-controlada-final.py --plan /home/magaton/DevLite-OS/docs/evidencias/plano-limpeza-final.json --plan-sha256 c0b96d65c99c175f7ccb0d2869579717dc700a7eb80b5625a66df0c083458c90 --execute-authorized
```

Sudo permanece necessário para a leitura integral dos metadados privados/processos e remoção dos arquivos root-owned somente nos [21 caminhos revisados](limpeza-final-proposta.md). O controlador faz todos os guards antes de excluir; uma referência ativa continua interrompendo a operação e agora deixa diagnóstico completo. Qualquer alteração nos hashes requer nova revisão.

A evidência e a proposta anteriores são preservadas como histórico; esta revisão substitui seus hashes de código de limpeza, sem alterar o plano de aquisição.
