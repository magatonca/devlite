# Plano acelerado — 19/11/2026

## Resultado atual

Limpeza aprovada concluída: 43 candidatos removidos, aproximadamente 8,36 GiB recuperados. Não repetir. ISO oficial e homologada, fontes, caches necessários e imagens aceitas preservados. Navegador já instalado nas visões Base/Live de work/release-browser-2f24tvsg. Contrato e 51 hashes de código conferidos nesta preparação; os hashes dos grandes artefatos foram conferidos na limpeza, sem repetir a leitura completa. Seis hashes do payload Modern conferidos. Suíte após limpeza: 489 testes aprovados; reports/testes-pos-limpeza-plano-acelerado.txt.

## Espaço e decisão

Livre na medição: 57.20 GiB. Empacotamento existente: 52.16 GiB, orçamento anterior que precisa ser recalculado após o visual. Cópias Base/Live estimadas por dados alocados: 10.07 GiB. Depois delas sobrariam 47.13 GiB: faltariam 5.02 GiB para o empacotamento.

Sem depender da preservação da esparsidade, reservar até 24 GiB para as duas imagens de 12 GiB: ponto de partida conservador 76.16 GiB livres, antes de crescimento e arredondamentos. Recomenda-se pelo menos 80 GiB livres. Disco observado por lsblk: /dev/xvda, 130 GiB; /dev/xvda3 ocupa quase todo o restante além do boot e o LV ocupa quase todo o PV. Não há indicação de espaço físico suficiente para ampliar apenas o LV.

Recomendação: expandir o disco virtual para pelo menos 160 GiB no hipervisor; isso deve acrescentar cerca de 30 GiB, com livre projetado de aproximadamente 87 GiB após expansão autorizada do filesystem. Não é medição nem garantia do orçamento final da ISO. Não apagar mais artefatos protegidos para compensar. Nenhuma operação de armazenamento executada nesta preparação.

## Escopo mínimo da candidata

- Reutilizar o navegador Epiphany nativo já instalado: desktop/helper/MIME conferidos anteriormente; lançamento gráfico, sandbox, navegação e persistência da nova composição ainda pendentes.
- Aplicar somente Modern: Greybird-dark, elementary-xfce-dark, painel XFCE nativo inferior com plugins preservados, wallpaper e LightDM. Sem pacotes, docks ou serviços novos. O protótipo não foi aplicado.
- Manter o Control homologado. Control 2.0 continua protótipo com backend simulado; não cumpre critérios para substituição nesta candidata.
- Deixar Adminer fora desta candidata. Upstream adquirido e validado sintaticamente anteriormente; wrappers novos, integração Apache/PHP, acesso IPv4/IPv6, rejeição externa e login real ainda pendentes. Não reduzir esses gates para incluí-lo.

## Bloqueios técnicos e aplicação Modern

Além do espaço, falta concluir e testar o adaptador de aplicação do Modern, com contrato novo específico. O adaptador do navegador sela visual_changes=false; não pode ser reutilizado como se autorizasse esta operação. Preparação necessária: ler as configurações efetivas das duas visões em montagens privadas somente leitura, renderizar patches com preimages por visão, preservar atalhos/menu/serviços/instalador, adaptar devlite-first-session que hoje fixa Greybird, ativar wallpaper por monitor real e o perfil dconf, respeitar keep-user-settings e perfis existentes. O rascunho de payload não substitui essa análise.

Após isso, executar em cópias privadas sequenciais, preservando as imagens aceitas. Exceção de escrita somente no job, ProtectSystem=strict e ProtectHome=read-only, sem rede, cgroups e limites de compressão existentes. Auditar todas as alterações por allowlist, metadados, dpkg/APT e componentes protegidos. Reconstruir delta da diferença das visões completas, não editar os dois SquashFS independentemente. Round-trip e prova kernel de composição obrigatórios.

## Comandos privilegiados para diagnóstico da expansão — não executados

Aprovação específica necessária antes destes comandos somente leitura:

```bash
sudo /usr/sbin/pvs --units b --nosuffix -o pv_name,pv_size,pv_free
sudo /usr/sbin/vgs --units b --nosuffix -o vg_name,vg_size,vg_free
sudo /usr/sbin/lvs --units b --nosuffix -o lv_path,lv_size,vg_name
```

Os comandos de alteração de partição/PV/LV/filesystem serão apresentados somente após a expansão no hipervisor e conferência do layout real. A expansão altera o hospedeiro e precisa de autorização específica. Ainda não há comando de aplicação Modern ou empacotamento selado pronto para aprovação: não executar comandos antigos de jobs diferentes.

## Condições para empacotar e gerar a ISO

Espaço suficiente medido para o job real, adaptador Modern aprovado e testado, execução privilegiada explicitamente autorizada, par resultante aceito atomicamente, navegador e configurações em ambas as visões, serviços e instalador preservados, manifests/catálogo atualizados, round-trip/composição aprovados, fontes originais inalteradas e suíte completa aprovada imediatamente antes da geração.

Recalcular o gate próprio da ISO: 2*tamanho_ISO_original + 3*tamanho_das_camadas_publicadas + 10 GiB, conforme executor existente, após os intermediários que permanecerem. Não presumir que passar no gate de compressão garante passar neste gate posterior.

Gerar uma única candidata somente após aprovação específica; não alterar a ISO homologada. Boot/instalação BIOS/UEFI da homologada são evidências anteriores, não homologação da composição nova. Validar a nova candidata em sessão gráfica Live e instalada, navegador, visual, ferramentas e reinício, com registro dos testes externos pendentes. Não prometer conclusão até o prazo sem executar esses gates.
