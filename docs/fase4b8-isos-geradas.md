# Fase 4B.8 — duas ISOs geradas e reprodução aprovada

18/11/2026 UTC. **Operação autorizada concluída com retorno 0: duas ISOs estruturalmente verificadas e idênticas bit a bit.** Boot e instalação em VM ainda não executados. Perfil: ubuntu-experimental.

## Artefatos reais

Nome: devlite-os-1.0-ubuntu-experimental.iso. Cada arquivo tem **3.550.609.408 bytes**, aproximadamente **3,307 GiB**.

| Construção | Caminho completo |
|---|---|
| Primeira, referência para os testes | `/home/magaton/DevLite-OS/artifacts/release-c0srssh8/devlite-os-1.0-ubuntu-experimental.iso` |
| Segunda, reprodução preservada | `/home/magaton/DevLite-OS/artifacts/release-22snj8_v/devlite-os-1.0-ubuntu-experimental.iso` |

SHA-256 comum, calculado a partir dos arquivos durante as construções e comparado pelo executor:

```text
7f49f8b03ad0201f70c5deed4879ffedb79bf7b7a3f1f105ca8380be8da3e4db
```

[Primeiro relatório](../artifacts/release-c0srssh8/release-report.json), [segundo relatório](../artifacts/release-22snj8_v/release-report.json) e [prova bit_identical](../artifacts/release-22snj8_v/reproducibility.json). Cada diretório também contém SHA256SUMS. Os campos individuais de relatório que pedem segunda construção registram o estado no instante de sua emissão; a prova reproducibility.json é o resultado posterior da comparação entre ambos.

## Validações efetivamente aprovadas em ambas

- ISO oficial revalidada por SHA-256 antes e depois de cada montagem da ISO.
- Boot híbrido BIOS/UEFI, parâmetros El Torito e metadados híbridos comparados com a fonte; volume UUID preservado, rótulo DevLite OS 1.0 Experimental.
- Imagem EFI anexada de **5.201.920 bytes** preservada por comparação criptográfica. Posição na ISO resultante: offset 3.545.067.520.
- Árvores externas extraídas em espaço de usuário e comparadas; somente os arquivos declarados foram alterados/adicionados. UID/GID/modos e demais metadados ISO conferidos.
- Payloads SquashFS/manifests/GRUB e proveniência iguais aos arquivos preparados; componentes não alterados do instalador preservados.
- **194 entradas MD5** e **dois checksums SHA-256 das camadas** conferidos em cada ISO.
- Proveniência GPG original: Good signature, chave Ubuntu CD Image Automatic Signing Key (2012), fingerprint **843938DF228D22F7B3742BC0D94AA3F0EFE21092**. Essa assinatura autentica os checksums originais arquivados; os checksums personalizados não foram assinados como Ubuntu.
- Segunda construção com as mesmas entradas seladas e PYTHONHASHSEED=0: SHA-256 exatamente igual. A prova cobre a montagem da ISO a partir dessas camadas, sem reexecutar APT ou recomprimir os sistemas de arquivos nesta rodada.

A composição real Base + delta e a integridade completa dos SquashFS já haviam sido aprovadas na [integração](fase4b8-integracao-aprovada.md). Não houve boot de uma VM durante as verificações estruturais.

## Conteúdo e limites

Base instalada preparada: 1.393 pacotes APT; visão Live: 1.534 pacotes APT. Os três registros Snap foram preservados com nome/canal/revisão, incluindo Desktop Bootstrap. As camadas incorporam idioma pt-BR, teclado ABNT2, fuso America/Sao_Paulo, identidade DevLite OS e os pacotes Ubuntu anteriormente instalados/auditados. Os serviços de desenvolvimento mantêm os perfis e máscaras preparados.

Esta é a edição **Ubuntu experimental**. Node.js LTS, TypeScript e VS Code continuam pendentes. Inicialização, funcionamento visual XFCE, captura Wireshark, aplicações, instalação real e persistência pós-instalação exigem os ensaios de aceitação em VM. Secure Boot não foi testado.

## Execução, host e recursos

Controlador: scripts/gerar-isos-controladas.py, como magaton, com --two-builds --execute-authorized. [Registro do controlador](../work/release-63m6oz2_/iso-control-h4ftqrmr/execution.json). Contrato bc32e0ce9fb1a95d4b0170c1130f46ec523ddee0871b9fd3915e8f126a91d19d.

Nenhum sudo dentro do construtor, mount, namespace, chroot, download, instalação de pacotes, limpeza, criação de VM ou commit. Original, ISOs anteriores, par ext4 aceito, cache dos 243 debs, contratos e evidências preservados. As árvores de auditoria e ambas as novas ISOs também ficaram preservadas.

Hashes críticos do Ubuntu Server iguais ao checkpoint inicial; sem montagens/loops do projeto residuais. Gate iso_final_autorizada restaurado false e demais gates de execução false. **197 testes automatizados aprovados** após as duas construções, verificador do projeto com zero erros e git diff --check aprovado. Relatório: reports/testes-apos-duas-isos.txt.

Livre medido: **22.02 GiB**. O guard por nova construção continua **22.50 GiB**; portanto outra construção deverá ser bloqueada com o espaço atual até recuperação de espaço aprovada ou expansão. Nenhum limite foi reduzido e nenhuma limpeza foi feita. Os testes previstos no Windows não criam discos dentro deste Ubuntu Server.

[Evidência consolidada da execução, host e hashes](evidencias/geracao-isos-execucao.json).

## Próximo passo

[Executar o laboratório de aceitação com a ISO de referência](fase4b9-validacao-pratica.md), mediante autorização própria para criar/iniciar VMs e instalar nelas. O checklist já está vinculado ao caminho e SHA-256 reais e seus 131 itens/documentações pendentes são corretamente rejeitados pelo validador. Nenhum desses testes foi marcado como aprovado automaticamente.

Verificações finais: as duas ISOs e a original estão ignoradas pelo Git. O CLI de aceitação recusou corretamente os 131 itens/evidências pendentes, sem divergência de ISO/SHA-256; saída em reports/aceitacao-real-pendente.txt.
