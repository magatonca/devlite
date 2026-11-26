# Navegador aplicado — resultado da execução autorizada

A autorização geral do usuário foi utilizada para adquirir e validar os dez debs fixados e executar o contrato isolado `release-browser-2f24tvsg`, SHA-256 `743d4a621b1a2837ffa6612257842c591283abebff64f8faef0ad5886c8073b1`.

**GNOME Web/Epiphany instalado nas duas cópias completas Base/Live, com par aceito.** Dez pacotes novos por visão, sem upgrades/remoções. Probes reais passaram antes do APT; simulação e preflight dos caminhos dpkg coincidiram com o lock. Instalação offline, policy temporária restaurada e nenhum processo extra no guest. Dpkg/APT, arquivos dos pacotes, bibliotecas, schemas, desktop entry, helper XFCE e MIME passaram. Inventários protegidos do instalador/boot/snap e /etc/systemd permaneceram iguais. E2fsck somente leitura das duas cópias passou; fontes aceitas originais foram novamente hasheadas e preservadas.

Os seis defaults foram mesclados com conferência de pré-imagem: helpers epiphany e MIME HTML/XHTML/HTTP/HTTPS para org.gnome.Epiphany.desktop. A aplicação não altera preferências explícitas de perfis existentes. **Não houve lançamento gráfico ou teste de persistência após instalação.** O navegador ainda não está na ISO homologada nem nos SquashFS publicados antigos.

## Saídas aceitas

Ambas são imagens ext4 de filesystem de trabalho, com 12 GiB lógicos, não discos de VM instalados/bootáveis:

- `work/release-browser-2f24tvsg/attempt/base.ext4`: SHA-256 `dcd5692cc7cfbb1a50487b1d332842a46d8184eff729b4528368484a11b44ded`.
- `work/release-browser-2f24tvsg/attempt/live.ext4`: SHA-256 `91bc8a6b4b042c151a56fd70c91c54fcccd702b4e76027fb03157a3eb856b676`.

Recibo root-owned 0444: `work/release-browser-2f24tvsg/browser-result.json`. Par e estado aceitos em attempt, mantidos privados. Unidade terminou com exit 0 após aproximadamente 63 minutos, com limites de 2,5 GiB RAM/1 GiB swap/uma CPU/128 tarefas. O tempo incluiu múltiplos hashes integrais das imagens e cópias, não apenas instalação APT. Nenhuma reinstalação é necessária para a próxima tentativa de empacotamento: reutilizar este par e seu lock, sem executar novamente o job.

## Auditoria somente leitura

A auditoria separada `browser-final-audit-30pydqpr`, contrato `9c6c5469da7eb02bba85c38ff5daaffb6fcaf184ec2647de37a6dd43d87fbf0e`, também terminou com exit 0. Montou fontes ro,noload,nodev,nosuid,noexec em namespace privado, sem executar programas dos alvos. Conferiu **5.292 arquivos do payload público por visão**, incluindo Node.js/TypeScript, Control, menu e identidade visual anteriormente implantados, comparando conteúdo e metadados com o manifesto original autenticado. Diretórios compartilhados não tiveram modo imposto nem foram alterados. Não repetiu hashes integrais dos raw: conferiu fingerprints antes/depois e os arquivos selecionados. Evidência: `work/browser-final-audit-30pydqpr/result.json`.

Arquivos críticos monitorados do host e config/projeto.json permaneceram iguais; quatro fontes do Control atual preservadas. Metadados das ISOs protegidas comparados ao recibo anterior, sem nova alegação de hash integral delas. Nenhuma unidade dos jobs ficou ativa, nem referência de mount/loop desses jobs no host. Nenhum pacote foi instalado no Ubuntu Server e nenhuma configuração administrativa global foi habilitada.

## Bloqueio atual de armazenamento

A fórmula existente do pack é 3×Base + 5×Live + 10 GiB, pelos bytes alocados medidos nas visões. Resultado: **52,16 GiB necessários**, contra aproximadamente **48,86 GiB livres**. Faltam **3,30 GiB**, antes de margem adicional recomendada. O gate inicial de integração de 32 GiB não substitui esse teste dinâmico mais restritivo. Nenhum limite foi reduzido; nenhuma reconstrução, compressão, limpeza ou ISO foi iniciada. Preservar o par novo, imagens anteriores, caches, código e evidências. Resolver armazenamento antes de criar pack-attempt ou novas cópias.

## Adminer e Control 2.0

Adminer Ubuntu 4.8.1-2 adquirido somente para inspeção, com tamanho/hash do índice assinado conferidos. Seu Alias padrão /adminer → /etc/adminer usa Require all granted; proposta foi reforçada para negar rota/árvores nativas e permitir somente o wrapper próprio em loopback IPv4/IPv6. A versão Ubuntu permanece sem aprovação de segurança para inclusão padrão.

Adminer 6.3.0 MySQL multilíngue também adquirido para revisão: 441.747 bytes, SHA-256 `33af3816a08213ae7579f8416e66d7d70054d6bcd70516d4ad3124f4b8b5c1e0`, correspondente ao asset.digest publicado pela API oficial GitHub sobre HTTPS. O commit consultado é unsigned; não há assinatura GPG independente verificada. Foram preservados 22 advisories públicos e as versões corrigidas declaradas. Isso não homologa compatibilidade dinâmica nem segurança completa. **Nenhuma versão Adminer foi instalada ou executada como PHP**, nenhum usuário de banco criado e nenhuma credencial salva pelo Control.

Control 2.0 permanece protótipo separado com backend simulado e opção Gerenciar bancos de dados. O Control homologado continua preservado. Nenhum visual Modern foi aplicado às imagens.

## Testes e próximo passo

**479 testes automatizados aprovados**, log `reports/testes-execucao-geral-final.txt`. Além deles, a instalação real, ambos os probes, auditorias guest, e2fsck e auditoria readonly de payload passaram. Interface gráfica, navegação HTTP/HTTPS, persistência pós-instalação, Control 2.0 real, Adminer em PHP/MariaDB, boot/instalação de uma nova candidata e visual novo continuam pendentes.

Próximo bloqueio técnico: recuperar/prover ao menos 3,30 GiB mais margem sem apagar fontes protegidas, depois selar integração que reutilize o par aceito e gere/reconcilie as camadas com manifests atualizados. A autorização geral está registrada; esta execução não autoriza por inferência uma exclusão de caminhos antigos fora da lista de limpeza já aprovada. Nenhum artefato foi apagado para contornar o limite. Gerar a ISO somente após as integrações e validações correspondentes; não declarar versão final homologada.

Evidência consolidada: `docs/evidencias/execucao-geral-concluida.json`.

## Checagem real de sintaxe PHP 8.3 — sem instalação Adminer

O contrato `adminer-php-check-w5tie5iq`, SHA-256 `4b041eafc1a367673d82fc41dadc3c9b3cd179f450a372b4d94cad426587356e`, foi executado sob a autorização geral e terminou com exit 0. Montou a nova Base ro/noload/nodev/nosuid; o supervisor fez chroot antes de criar o compilador. O compilador rodou como UID 65534, capabilities zeradas e no_new_privs, com flags fixas `php8.3 -n -v` e `php8.3 -n -l` sobre cópia root-owned do Adminer, validada pelo SHA-256 e bind somente leitura. Não houve avaliação do código PHP de aplicação, HTTP ou banco.

Resultado: **PHP 8.3.6** e **No syntax errors detected** no Adminer 6.3.0 MySQL multilíngue. Isso valida a sintaxe no engine real do alvo; não valida extensões carregadas em SAPI Apache, login MariaDB, consultas, regras HTTP ou sessão gráfica. Recibo root-owned 0444 em `work/adminer-php-check-w5tie5iq/result.json`. Os mounts e tmpfs terminaram com o PID namespace; imagens e arquivos críticos do host permaneceram preservados. Nenhuma credencial ou usuário de banco foi criado.
