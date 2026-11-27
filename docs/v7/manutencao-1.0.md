# Manutenção pós-instalação da DevLite OS 1.0

## Homologação registrada

O usuário confirmou a instalação no Itautec Infoway W7430 com Core i3 M380, 6 GB de RAM e SSD de 120 GB. Instalador personalizado, Firefox, DevControl, VS Code, Apache, MariaDB e Adminer funcionaram. O ícone do Whisker configurado pela interface gráfica persistiu após reiniciar.

Imagem preservada em `artifacts/devlite-v7-d1l865re/devlite-os-1.0-amd64.iso`, com SHA-256 `1f05637dc3c3fd668543977811bc720a42d62f4df6712bcf6678d11ac9d1ce21`.

## Inicialização e desktop

- A extração da ISO mostra entradas DevLite no GRUB regular e no GRUB de loopback. O boot híbrido usa GRUB em BIOS e UEFI. Os módulos `syslinuxcfg.mod` pertencem ao GRUB. A árvore não contém um lançador ISOLINUX ou SYSLINUX.
- O initrd Live herdado inclui os temas gráfico e texto do Xubuntu. As novas entradas Linux do GRUB passam `nosplash` para evitar o tema herdado. Um splash DevLite no início do Live exigirá gerar um initrd próprio em futura manutenção da mídia. A exibição no notebook é compatível com o tema encontrado no initrd.
- O Plymouth do sistema em camadas já aponta para os temas DevLite. Os initramfs locais podem ser regenerados com os temas instalados para aplicar a identidade no boot e no desligamento. O drop-in do GRUB nomeia a entrada do sistema e as entradas avançadas e de recuperação geradas por ele.
- O LightDM aponta para o fundo DevLite. O instalador personalizado permanece o validado no notebook. `.disk/info`, os identificadores de origem do instalador, as configurações de sessão e os nomes de pacotes mantêm a identificação técnica da base Xubuntu/Ubuntu. EFI, kernel, assinaturas e mecanismos de atualização permanecem preservados. Secure Boot e a aparência das novas configurações de boot seguem sem homologação.
- XFCE carrega `xfce4/panel/default.xml` conforme o perfil XDG. O painel padrão usa a disposição testada na base, com Whisker à esquerda e o separador expansível antes dos indicadores e do relógio. O Whisker instalado usa Xfconf no canal do painel, sob `/plugins/plugin-<ID>`. O novo painel preenche essas propriedades no plugin padrão. O Whisker também carrega `xfce4/whiskermenu/defaults.rc` e reconhece o arquivo legado por instância para migração. O atalho Live deixa de reescrever esse arquivo e reiniciar o painel. Os padrões dos dois perfis e o contraste do terminal se aplicam a contas sem configuração pessoal.

## Aplicar ao notebook

Execute na raiz de uma cópia revisada do projeto no notebook. Os comandos copiam arquivos de configuração e preservam os perfis pessoais existentes. Se houver uma configuração administrativa personalizada em algum destino, revise-a antes de substituí-la.

```sh
(
set -eu
v7_overlay=v7/overlay
v6_overlay=v6/overlay
panel=etc/xdg/xdg-xubuntu/xfce4/panel/default.xml
branding=etc/default/grub.d/99-devlite-branding.cfg

test -r /usr/share/icons/hicolor/scalable/apps/devlite.svg
sudo install -D -m 0644 "$v7_overlay/$panel" "/$panel"
sudo install -D -m 0644 "$v7_overlay/$panel" /etc/xdg/xfce4/panel/default.xml
for xdg in etc/xdg etc/xdg/xdg-xubuntu; do
    whisker="$xdg/xfce4/whiskermenu/defaults.rc"
    terminal="$xdg/xfce4/terminal/terminalrc"
    sudo install -D -m 0644 "$v6_overlay/$whisker" "/$whisker"
    sudo install -D -m 0644 "$v7_overlay/$terminal" "/$terminal"
done
sudo install -D -m 0644 "$v7_overlay/$branding" "/$branding"
sudo update-grub
)
```

Para atualizar o splash local, confira primeiro os temas em uso. Se os dois apontarem para `themes/devlite/`, regenere os initramfs instalados.

```sh
readlink -f /usr/share/plymouth/themes/default.plymouth
readlink -f /usr/share/plymouth/themes/text.plymouth
sudo update-initramfs -u -k all
```

### Mousepad

Instale o pacote do Ubuntu 24.04. O Mousepad inclui tradução pt-BR e uma entrada própria em Acessórios. O VS Code pode continuar como editor de desenvolvimento. [Pacote oficial](https://packages.ubuntu.com/noble/mousepad)

```sh
sudo apt-get update
sudo apt-get install mousepad
```

Para o padrão de novas sessões DevLite, execute `sudoedit /etc/xdg/xdg-xubuntu/xfce-mimeapps.list` e defina `text/plain=org.xfce.mousepad.desktop;` em `[Default Applications]`, preservando as demais linhas. Para aplicar também à sua conta atual, execute na sessão gráfica, como usuário comum:

```sh
xdg-mime default org.xfce.mousepad.desktop text/plain
xdg-mime query default text/plain
```

A mídia 1.0 preservada não contém Mousepad. A inclusão offline em uma próxima mídia depende de adicionar o pacote oficial e suas dependências ao conjunto de entradas offline.

### Adminer

No DevControl, abra **Desenvolvimento → Gerenciar banco de dados**. O botão informa quais serviços estão inativos. Se precisar iniciar ambos para a sessão atual, use `sudo systemctl start apache2 mariadb`. O endereço é `http://127.0.0.1:8081/devlite-adminer`. A configuração também aceita loopback IPv6 e bloqueia a autenticação com contas administrativas reservadas.

Crie uma conta local separada por projeto pelo cliente administrativo. Execute `sudo env MYSQL_HISTFILE=/dev/null mariadb` e digite o SQL interativamente com uma senha longa e exclusiva gerada pelo seu gerenciador de senhas. Substitua o texto entre aspas antes de executar.

```sql
CREATE DATABASE projeto_exemplo CHARACTER SET utf8mb4;
CREATE USER 'projeto_exemplo'@'localhost' IDENTIFIED BY 'SUBSTITUA_POR_UMA_SENHA_EXCLUSIVA';
GRANT ALL PRIVILEGES ON projeto_exemplo.* TO 'projeto_exemplo'@'localhost';
```

No Adminer, a conexão é fixada em **localhost**. Informe o usuário **projeto_exemplo**, a senha escolhida e banco **projeto_exemplo**. Repita com nomes e senhas diferentes para cada projeto. A conta tem privilégios apenas sobre seu banco.

## Atualizações DevLite

A DevLite 1.0.1 usa Git para o código e um único pacote `devlite-update` distribuído por GitHub Releases. Consulte [assinar, instalar e recuperar a atualização](atualizacao-1.0.1.md). O roteiro manual acima continua disponível para instalação seletiva.

Para as próximas melhorias do painel de monitoramento, mantenha o coletor assíncrono atual e consulte `/proc/stat`, `/proc/meminfo`, `/sys/class/hwmon` e `/sys/class/power_supply` enquanto a janela estiver aberta. Use `systemd-analyze time` para tempo de boot, `systemctl` para serviços ativos ou falhos e os logs do APT para histórico. Mostre sensores indisponíveis como tal. Temperatura de discos que exigirem acesso administrativo fica indisponível até existir uma operação específica autorizada. Preserve a execução sem um daemon de coleta.
