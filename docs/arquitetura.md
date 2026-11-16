# Arquitetura proposta

Remasterização controlada da ISO oficial, em VM de construção descartável. O host Ubuntu Server é estação de trabalho; suas configurações, pacotes e identidade não devem ser copiados para a imagem. Uma ISO remasterizada não herda automaticamente todas as garantias de suporte da base.

## Etapas futuras e contratos

1. **Preflight sem privilégios:** validar arquitetura, espaço, memória, ferramentas, configuração e diretório de trabalho exclusivo. Produzir relatório; abortar se faltarem requisitos.
2. **Aquisição autorizada:** obter ISO e metadados oficiais; validar a assinatura de SHA256SUMS com chave Ubuntu cuja impressão digital seja conferida por fonte independente; conferir SHA-256 da ISO. Registrar URL, data, tamanho, hash e impressão digital. Nenhuma execução com entrada não autenticada.
3. **Inspeção:** extrair árvore ISO com xorriso; identificar layouts Casper, squashfs, instalador, boot BIOS/UEFI e metadados reais. Não supor um único squashfs. Fixar inventário da entrada e decidir como preservar o instalador.
4. **Customização isolada e autorizada:** extrair filesystem em VM descartável com privilégios apenas nela. Montagens de /proc, /sys, /dev e resolução DNS têm ciclo de vida explícito e desmontagem em falha. Bloquear inicialização de daemons durante instalação e restaurar política ao finalizar. Nunca bind-mount de /home do host. Adicionar pacotes e overlay revisados; registrar versões e origens.
5. **Higienização:** remover caches, temporários, histórico, credenciais, identidade da máquina e chaves SSH de host; garantir regeneração no sistema instalado. Não remover componentes essenciais do instalador. Auditar pacotes e serviços.
6. **Empacotamento:** gerar squashfs com limite inicial de 1 processo e orçamento de memória; atualizar tamanhos, manifests e checksums internos conforme o layout observado. Reconstruir ISO usando parâmetros de boot extraídos da original, preservando boot híbrido BIOS/UEFI e rótulos coerentes. Não prometer Secure Boot sem ensaio.
7. **Validação:** comparar inventários; testar live e instalação completa em VMs BIOS e UEFI. Testar persistência das customizações após instalação e reinicialização.
8. **Entrega:** ISO, SHA256SUMS, manifest de pacotes, relatório de testes, receitas/configuração, licenças e proveniência. Assinatura de entrega somente com chave de distribuição definida separadamente.

## Automação

Orquestrador futuro em Python 3.12, com comandos explícitos por etapa, logs sem segredos e código de saída diferente de zero em falha. Não haverá construção no import nem instalação automática de dependências. Downloads e operações privilegiadas exigem portas de aprovação separadas; autorização não é inferida de um arquivo de configuração.

Etapas devem validar pré-condições e permitir retomada apenas com hashes de entrada correspondentes. Limpeza futura atua somente no workspace registrado e exige proteção contra caminho vazio, /, links simbólicos e volumes externos. Usar finalização garantida para desmontar recursos; falha não autoriza apagar evidências.

Registrar versões efetivas dos pacotes e ferramentas. Reprodutibilidade inicial significa receita e proveniência auditáveis; igualdade binária depende de fontes fixadas, timestamps e repositórios preservados, a validar posteriormente.
