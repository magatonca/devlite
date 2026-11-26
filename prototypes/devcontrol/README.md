# DevControl 1.0 — MVP gráfico isolado

Aplicativo GTK3 em português brasileiro para consultas locais de sistema, rede,
ferramentas de desenvolvimento, Docker, VPN, aparência XFCE e manutenção.
O MVP não executa operações administrativas, não inicia serviços, não altera
configurações, não acessa a rede e não armazena resultados.

## Executar

Em uma sessão gráfica XFCE com Python 3, PyGObject e GTK3:

```sh
python3 prototypes/devcontrol/app.py
```

O host de desenvolvimento não tem o namespace Gtk disponível, portanto a janela
não pode ser renderizada neste ambiente sem instalar dependências. Os manifests
Base/Live registrados no projeto incluem `python3-gi` e `gir1.2-gtk-3.0`.

## Consultas e limites

- Comandos são fixos, usam `shell=False`, ambiente restrito, timeout de 3 s e
  limite de saída; falhas e dependências ausentes são exibidas por seção.
- A UI coleta em uma thread de trabalho, sem bloquear o loop GTK.
- Docker usa apenas `docker ps`; não altera serviços nem contêineres.
- Atualizações consultam apenas o cache local via `apt-check`; não atualizam
  índices nem acessam repositórios.
- Firewall e serviços são consultados por `systemctl show`. Uma unidade ausente,
  sem systemd ou sem permissão aparece como indisponível.
- VPN ativa é inferida das conexões VPN que o NetworkManager reporta; não
  inspeciona arquivos de perfil ou credenciais.
- Nenhum valor é persistido. Saídas de contêineres e informações de rede são
  mostradas somente na janela local.

## Testes

```sh
python3 -m unittest discover -s tests -p 'test_devcontrol.py' -v
```

## Integração na próxima ISO candidata

`manifest.json` descreve os caminhos instalados e as dependências de runtime.
A entrada de menu aponta para `/usr/lib/devlite/devcontrol/app.py`. O aplicador
`scripts/empacotar-modern-candidata.py` verifica as imagens Modern aceitas,
clona Base/Live em um job isolado, confirma GTK/PyGObject já empacotados e
adiciona o DevControl e o lançador oficial do VS Code. O atalho e o drop-in do
instalador são adicionados somente à visão Live; o serviço e seu `ExecStart`
permanecem intactos.

Não instalar usando o overlay histórico do Control nem substituir
`devlite-control`, seu helper ou sua policy do Polkit. O gerador
`scripts/gerar-iso-modern-candidata.py` produz uma única ISO candidata em um
diretório novo e mantém a ISO aprovada anterior inalterada. A aprovação final
depende de testes manuais no Hyper-V (BIOS/UEFI, Live, instalador, sistema
instalado, DevControl e persistência); nenhum build substitui essa homologação.

Se a sessão de automação não compartilhar a autenticação sudo do host, execute
`bash scripts/executar-modern-candidata-manual.sh <job> <sha256-do-contrato>`
no terminal autenticado de `magaton`. O script refaz os gates de host, job,
espaço, ISO aprovada e worker ativo, solicita autenticação pelo sudo normal e
grava a saída em um log separado no workspace.
