# Fase 4B.9 — roteiro prático da ISO gerada

> Candidata pública atual: ver [ISO verificada e roteiro de transferência](iso-publica-candidata-concluida.md). Os caminhos e resultados abaixo preservam o perfil experimental histórico; para homologar a edição pública, usar a candidata e seu registro público.

**Preparado; nenhuma VM criada/iniciada e nenhuma instalação executada.** O laboratório segue o [plano existente da Fase 3A](fase3a-testes-iso.md), agora com a ISO DevLite gerada. Criação de VMs, boot e instalação exigem autorização específica; o executor desta rodada não os realizou.

## Artefato para o laboratório

ISO de referência: `/home/magaton/DevLite-OS/artifacts/release-c0srssh8/devlite-os-1.0-ubuntu-experimental.iso`.
Tamanho: 3550609408 bytes. SHA-256:

```text
7f49f8b03ad0201f70c5deed4879ffedb79bf7b7a3f1f105ca8380be8da3e4db
```

A segunda cópia idêntica foi removida na limpeza autorizada; sua reprodução bit a bit permanece registrada nas evidências históricas.

Exemplo para transferência manual no PowerShell do Windows, após autorização para o laboratório: substituir IP_DO_UBUNTU pelo mesmo destino usado no SSH e executar em um diretório próprio de testes. Não executar os exemplos desta seção no Ubuntu Server.

```powershell
scp magaton@IP_DO_UBUNTU:/home/magaton/DevLite-OS/artifacts/release-c0srssh8/devlite-os-1.0-ubuntu-experimental.iso .
Get-FileHash .\devlite-os-1.0-ubuntu-experimental.iso -Algorithm SHA256
(Get-Item .\devlite-os-1.0-ubuntu-experimental.iso).Length
```

Só usar a cópia se hash e tamanho coincidirem com os valores acima. Nenhuma transferência foi feita pelo agente.

## Ensaios previstos, ainda não executados

Reutilizar o procedimento VMware Workstation no Windows descrito na Fase 3A: duas VMs independentes, uma BIOS e outra UEFI, discos novos descartáveis de 40 GiB, 4 GiB RAM por VM e execução sequencial. Conferir os recursos do Windows antes de criar as VMs. Secure Boot fica fora deste ensaio. Usar um único disco virtual descartável em cada VM, sem discos físicos/raw ou disco da VM de desenvolvimento.

Para cada firmware: iniciar Live, registrar o firmware detectado, XFCE, pt-BR, ABNT2, horário/identidade, instalador e programas; instalar apenas no disco descartável; desligar, remover a ISO e reiniciar pelo disco; repetir verificações e conferir persistência após novo reboot. Registrar falhas e interromper em caso de disco/firmware inesperado, falha de checksum, boot ou instalador.

Os serviços de desenvolvimento devem manter as máscaras/perfis previstos; testar ativação manual somente no guest de laboratório. Conferir Writer/Calc/Impress, PDF, Remmina, integração VPN, política de captura Wireshark, PHP/extensões e Docker Compose conforme checklist. As checagens de programas pertencem à VM Live/instalada, sem instalar ou testar esses aplicativos no Ubuntu Server hospedeiro.

## Registros e critérios de aprovação

Modelo: work/release-63m6oz2_/acceptance-ubuntu-experimental.json. Comandos dos programas: work/release-63m6oz2_/program-checks.json. Os campos da ISO já apontam para o artefato de referência; todos os testes reais continuam pending.

Aprovar apenas com duas VMs e discos distintos identificados, firmware confirmado, todos os critérios do perfil ubuntu-experimental em passed, versões de programas registradas e evidências de cada teste em arquivos com SHA-256. Node.js LTS, TypeScript e VS Code são pendências explícitas da edição completa.

Após coletar e revisar as evidências manualmente, o validador documental existente pode ser executado como magaton, sem iniciar VM:

```sh
python3 /home/magaton/DevLite-OS/scripts/devlite-release.py --validate-acceptance /home/magaton/DevLite-OS/work/release-63m6oz2_/acceptance-ubuntu-experimental.json --iso-sha256 7f49f8b03ad0201f70c5deed4879ffedb79bf7b7a3f1f105ca8380be8da3e4db --evidence-root /home/magaton/DevLite-OS/work/release-63m6oz2_
```

No estado atual, esse comando deve recusar a aceitação porque faltam os testes e suas evidências. Um retorno documental favorável só atesta completude/integridade dos registros fornecidos; o conteúdo das evidências precisa de revisão humana. Não há aprovação atual de boot, instalação, XFCE funcional ou persistência.

## Preparação para distribuição pública

O [guia de instalação e coleta no guest](instalacao-devlite-1.0.md) acrescenta o coletor de evidências e o perfil público, preservando este modelo experimental. Decisão atual: Node.js/TypeScript obrigatórios no candidato final; VS Code oficial opcional, fora da ISO pública. Novos componentes e identidade visual já foram aplicados e integrados à candidata pública. Os testes reais continuam pendentes.
