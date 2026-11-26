# ISO pública candidata verificada

> Atualização: o usuário relatou aprovação dos testes Hyper-V BIOS/UEFI e das funcionalidades existentes, com ausência de navegador gráfico. Ver [correção preparada e situação atual](navegador-e-preparacao-visual.md). As pendências descritas abaixo registram o estado histórico da conferência feita pelo agente; nenhum resultado automático foi falsificado.

A execução única do contrato `b47bc900132ada42a80d33892f981e429dd42d2ff341dece185d4734599159fe` já estava concluída ao retomar. Foi reutilizada, sem gerar outra imagem. O recibo indica `candidate_structurally_verified`; o SHA-256 do relatório e uma nova leitura integral da ISO confirmaram os valores abaixo.

- Arquivo: `/home/magaton/DevLite-OS/artifacts/release-1hu5dx5v/devlite-os-1.0-amd64.iso`.
- Tamanho: **3.603.496.960 bytes** (aproximadamente 3,36 GiB).
- SHA-256: `2c699f3facb3f84ced392fd37bc25a9b7e46c74022c62816be2119af7f294d77`.
- Relatório: `artifacts/release-1hu5dx5v/release-report.json`.
- Evidência desta conferência: `docs/evidencias/iso-publica-verificada.json`.
- Espaço livre após a geração: aproximadamente **38,39 GiB**.

Estrutura BIOS/UEFI híbrida, EFI anexada, preservação de árvore/instalador, 195 entradas MD5 e dois checksums de camadas aprovados no relatório da geração. Node.js, TypeScript e personalizações foram integrados nas camadas auditadas. VS Code permanece opcional, fora da ISO pública. Arquivos críticos e configuração do host continuam íntegros e gates desabilitados. Não foram instalados programas nem criadas montagens nesta conferência.

## Próximo passo: laboratório Windows/VMware

A candidata ainda não foi homologada. Boot, instalação, login, XFCE, pt-BR, ABNT2, persistência e funcionamento dos programas continuam sem testes reais. Esta VM Ubuntu não tem QEMU nem /dev/kvm. Nenhuma VM foi criada ou iniciada.

Transferir manualmente a ISO ao Windows e conferir hash e tamanho, substituindo IP_DO_UBUNTU pelo endereço SSH. Executar no PowerShell do Windows, em uma pasta de laboratório:

```powershell
scp magaton@IP_DO_UBUNTU:/home/magaton/DevLite-OS/artifacts/release-1hu5dx5v/devlite-os-1.0-amd64.iso .
Get-FileHash .\devlite-os-1.0-amd64.iso -Algorithm SHA256
(Get-Item .\devlite-os-1.0-amd64.iso).Length
```

Usar duas VMs independentes, BIOS e UEFI, com discos novos descartáveis de 40 GiB, 4 GiB RAM e duas CPUs; testar sequencialmente. Não anexar discos físicos nem o disco do Ubuntu Server. Secure Boot fora do escopo inicial. Seguir o [guia de instalação](instalacao-devlite-1.0.md): Live, instalador, instalação no disco descartável, remoção da ISO, login e segundo reboot. Conferir Node.js, TypeScript, DevLite Control e demais programas tanto no Live como instalado.

O registro público foi preparado em `work/public-iso-1gj6j0xt/acceptance-public.json`, vinculado a esta ISO, com todos os 146 critérios ainda pendentes. O modelo histórico não foi alterado. Guardar evidências reais e hashes antes de preencher resultados. A geração única não comprova reprodução bit a bit da candidata. Nenhuma aprovação adicional de geração é necessária para usar este artefato nos testes manuais; o agente não executará VMs ou instalações sem autorização específica.

O validador documental foi executado sobre esse registro e retornou 1, como esperado, por ausência dos ensaios e evidências práticas. Saída completa em `docs/evidencias/aceitacao-publica-pendente.json`. Nenhuma homologação foi concedida.
