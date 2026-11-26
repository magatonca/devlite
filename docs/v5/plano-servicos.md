# Plano de serviços da v5

Somente planejamento. Não executar os exemplos abaixo no host nem na VM nesta fase.

## Três ambientes distintos

| Ambiente | Bloqueio de partida | Política final |
|---|---|---|
| Build isolado | `policy-rc.d` temporário com retorno 101; namespaces/cgroups, sem systemd do host | Preservar/restaurar policy anterior em finally; não publicar guard ou máscaras transitórias |
| Live | Instalador, Snap, rede e integração casper preservados | Ferramentas disponíveis; serviços de desenvolvimento desabilitados, sem máscaras herdadas; SSH servidor não é requisito do Live |
| Instalado | Políticas definitivas do produto, sem guard de build | Pacotes presentes, unidades carregáveis, partida manual possível; nenhum serviço de desenvolvimento habilitado automaticamente |

Disabled remove os vínculos de boot; masked impede também início manual/dependências. Static/alias/indirect não significam disabled. Até uma unidade disabled pode iniciar por dependências, socket, timer ou D-Bus: os testes devem cobrir ativadores e não apenas um resultado de `is-enabled`.

## Correção preparada para implementação

- Separar o contrato de bloqueio durante APT do contrato final. Preferir apenas o guard temporário quando suficiente. Se uma máscara transitória ainda for necessária, registrar precisamente quais links foram criados, preimages, modos/owners e restaurá-los em finally. Recusar sobreposição a uma configuração não reconhecida.
- Em novas visões v5, remover somente os links herdados DevLite para `/dev/null` da allowlist. Não apagar unidades vendor, aliases legítimos nem máscaras intencionais de máquinas existentes. Validar metadados e origem antes de remover uma máscara.
- Desabilitar vínculos de boot das unidades canônicas abaixo, sem `--now`. Não chamar enable, start, restart ou daemon-reload do systemd do host. Tratar aliases MariaDB/MySQL como o mesmo serviço; preservar o alias legítimo do pacote quando aplicável.
- Não exportar policy-rc.d temporário ou backups operacionais, nem deixar guarda permanente que impeça futuras atualizações no instalado.
- Remover a lógica de remascaramento do helper novo e ajustar/descontinuar o entrypoint legado para não reintroduzir a política antiga. Não remover o helper somente do menu e deixá-lo administrando o estado antigo silenciosamente.
- Acrescentar presets restritos quando úteis, sem `preset-all`; validar também o estado dos helpers Debian para que atualização de pacote não reative serviços que o usuário desabilitou.

| Unidade | Pacote/estado observado | Padrão proposto |
|---|---|---|
| apache2.service | apache2 instalado | unmasked, disabled, inactive; início manual permitido |
| mariadb.service | mariadb-server instalado | unmasked, disabled, inactive |
| mysql.service | máscara herdada de alias | sem máscara; alias vendor válido ou ausência justificada; não habilitar separadamente |
| docker.service | docker.io instalado | unmasked, disabled, inactive |
| docker.socket | docker.io instalado | unmasked, disabled, sem listener automático |
| containerd.service | containerd instalado | unmasked, disabled; deve iniciar quando solicitado por Docker |
| iperf3.service | máscara adicional confirmada | unmasked, desabilitado; preservar ferramenta CLI |
| ssh.service / ssh.socket | openssh-server ainda ausente | instalar no target v5; ambas unmasked e disabled |
| openvpn.service / instâncias | componente VPN existente | preservar perfis; distinguir umbrella de túneis reais e NetworkManager |
| php*-fpm.service | PHP-FPM ausente na v4 | oferecer controle somente se pacote/unidade instalados; PHP CLI não é daemon |

Comandos de manipulação, quando implementados e aprovados, devem usar raiz descartável canônica explícita: `systemctl --root=<RAIZ_ALVO> unmask ...`, `disable ...` e `is-enabled ...`. Não usar `show` como se fosse uma consulta completa ao manager offline. Fora do root descartável, apenas consultas. O contrato futuro precisa provar que a raiz é do projeto, não `/`.

## Docker e dependências

A unidade real pede socket e containerd e usa `/run/containerd/containerd.sock`. No início manual, conferir runtime não mascarado, solicitar containerd e aguardar sucesso; então iniciar Docker, deixando o systemd ordenar suas dependências. `Wants=containerd.service` sozinho não garante runtime disponível.

Parada deve tratar o socket para evitar reativação por cliente e avisar sobre contêineres/conexões. Não parar containerd compartilhado com Kubernetes/outros workloads automaticamente. Desabilitar boot não deve parar o que está em execução. Não habilitar containerd só para fazê-lo iniciar por dependência: disabled permite esse início.

Manter socket Unix restrito, sem TCP Docker e sem inclusão automática do usuário no grupo docker (acesso equivalente a root). Nenhuma máscara deve reaparecer após start, stop, restart, cancelamento ou erro.

## OpenSSH Server

A inclusão é nova na v5: resolver dependências no banco alvo e índices Ubuntu autenticados, sem instalar no host. Revalidar assinatura, versão, hash, arquitetura e transação antes da aquisição/instalação autorizadas. O cliente já existe; não confundir sua presença com servidor.

Durante instalação isolada, impedir partida por scripts de manutenção. Antes de publicar a imagem: ssh.service e ssh.socket desabilitados, sem máscaras e sem listener; auditar aliases e presets. O cloud-init presente pede `sshd.service`, e o instalador pode aplicar sua própria política SSH: verificar essa interação no primeiro boot, não presumir que disable basta. O código local cc_set_passwords somente reinicia em systemd se o serviço já estiver ativo, mas isso não elimina os demais ativadores.

Planejar configuração `PermitRootLogin no` em inclusão de precedência verificada. OpenSSH usa a primeira atribuição aplicável; validar o resultado com `sshd -t` e `sshd -T` incluindo casos Match, em alvo isolado. Não presumir que um arquivo `99-...` sempre prevalece. Não alterar o SSH do servidor de desenvolvimento. [Referência Ubuntu](https://ubuntu.com/server/docs/how-to/security/openssh-server/).

Chaves:

- Postinst pode gerar host keys mesmo que policy-rc.d impeça o daemon. Antes do empacotamento, verificar ausência de chaves privadas e remover somente chaves geradas na cópia descartável, por allowlist exata. Nunca apagar chaves da máquina de desenvolvimento ou do usuário.
- Gerar depois da cópia para cada instalação, com um único responsável: hook de finalização do instalador ou oneshot de primeiro boot específico do target. Se não houver hook comprovado, preparar oneshot com `ssh-keygen -A`, sem daemon residente, ordenado antes da ativação de ssh.service/ssh.socket. Não executar `-A` no build e depois distribuir suas chaves.
- Coordenar com cloud-init (que pode recriar host keys). Não regenerar a cada boot; comparar fingerprints de duas instalações e comprovar persistência numa mesma instalação. `ssh-keygen -A` cria os tipos de chave de host ausentes, conforme [manual Noble](https://manpages.ubuntu.com/manpages/noble/man1/ssh-keygen.1.html).
- Não incluir senhas, credenciais, authorized_keys de desenvolvimento nem chaves privadas na ISO. A futura ativação pelo Control exige autenticação administrativa e não abrirá regra de firewall automaticamente.

## Testes exigidos na Fase 2

Unidades vendor presentes e carregáveis; link `/dev/null` ausente na visão composta; boot flags disabled e ativadores coerentes; policy transitório restaurado mesmo em falha; APT/dpkg íntegros. Validar manualmente start/stop/restart de Apache, MariaDB e Docker numa VM autorizada, com provas de runtime/socket e segundo reboot sem autostart. Repetir após atualizar um pacote, para detectar reativação por maintscripts/presets.

Os testes antigos que exigem máscaras continuam sendo histórico, não foram alterados nesta fase. Criar testes específicos da política v5, incluindo falhas/cancelamento, em vez de apresentar a suíte antiga verde como prova da nova política.
