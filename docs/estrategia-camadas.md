# Estratégia de personalização após inspeção

A arquitetura geral continua adequada, com adaptação obrigatória para duas camadas e EFI anexada. A Fase 2 não autoriza construção ou alteração de filesystem. Estrutura comprovada em [relatório da Fase 2](fase2-aquisicao-validacao.md).

## Fase 3 — primeiro preservar o comportamento original

Após autorização, implementar reconstrução sem mudanças de pacotes, usando cópias separadas da ISO autenticada. Preservar kernel, initrd, hierarquia minimal → minimal.live, nomes, catálogo de fontes, boot GRUB, MBR/GPT e imagem EFI anexada. Reutilizar a estrutura de boot capturada pelo xorriso, com caminhos e tamanhos calculados na geração, nunca copiar offsets para uma ISO de tamanho novo. Não executar automaticamente o texto do relatório.

A primeira entrega deve iniciar live e instalar em VMs descartáveis BIOS e UEFI, com disco virtual dedicado, reiniciar sem mídia e validar a fonte instalada. A existência dos arquivos de boot não substitui esses ensaios. Secure Boot é ensaio separado. Nenhum disco do host deve ser alvo.

## Fase 4 — base instalada e live consistentes

1. Produzir uma base personalizada derivada de `minimal.squashfs`, mantendo UID/GID, permissões, xattrs e capabilities. Pacotes e personalizações que devem persistir após instalação pertencem à base, não apenas à folha live.
2. Produzir uma visão live sobre a nova base e reaplicar os componentes exclusivamente live. A folha atual sobrepõe inclusive `/var/lib/dpkg/status`, configurações e estado snap; reutilizá-la sem reconciliação pode esconder alterações e quebrar consistência APT. Inventariar conflitos de caminhos, whiteouts e diretórios opacos antes de decidir como regenerar o delta.
3. Estratégia preferida: regenerar uma camada live coerente com a nova base em ambiente de build autorizado e isolado. Preservar o instalador, snaps/seeds/assertions, serviços e arquivos live necessários. Não fundir a folha live na imagem instalada nem achatar as camadas por conveniência.
4. Reconstruir os manifests no formato esperado pela base real: inventários completos para auditoria e deltas por camada onde exigidos. Atualizar `.size`, `filesystem.size` e `install-sources.yaml` a partir das novas medições; preservar ID, tipo e caminho enquanto não houver razão testada para mudar.
5. Atualizar hashes internos (`/md5sum.txt`, `/casper/SHA256SUMS`) e hashes finais. Assinaturas oficiais internas só autenticam o conteúdo original: não mantê-las como se assinassem squashfs alteradas. Definir assinatura DevLite e política de verificação compatível com o instalador antes da release; não desativar silenciosamente verificações para contornar essa etapa.
6. Preservar o apontamento de `default-layer.conf`; se mudar a folha, tratar initrd e linha de boot de forma consistente. Alteração de kernel exige revisão conjunta de módulos, initrd e boot, fora do primeiro ensaio.

## Critérios de saída

Confirmar customização no live e após instalação; conferir APT/dpkg, locale, serviços, snaps do instalador, boot e ausência de arquivos do construtor. Só promover pipeline após reconstrução mínima passar na matriz de aceitação. O espaço atual permite o próximo laboratório, mas RAM de 3,8 GiB exige tarefas sequenciais, compressão inicial com um processo e medição de pico. Não executar compressão e VMs simultaneamente.

Referência conceitual: [Casper no Ubuntu Noble](https://manpages.ubuntu.com/manpages/noble/man7/casper.7.html). A seleção de folha documentada ali é complementada pela configuração efetivamente encontrada no initrd desta ISO.

## Atualização após autorização da Fase 3B

O usuário autorizou a reconstrução sem customização e adiou os testes manuais. A primeira ISO experimental passou pela auditoria estrutural, sem alteração de camadas ou pacotes. Ver [pipeline e resultados](fase3b-pipeline.md). Os critérios de boot e instalação acima continuam pendentes e não foram usados como alegação de compatibilidade comprovada.
