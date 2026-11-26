# Camada visual Modern v3

A candidata v3 usa um contrato ISO novo e uma camada SquashFS incremental. As
camadas Base/Live aprovadas, seus recibos e a ISO v2 permanecem somente leitura.

## Baseline do host

A baseline host v3 preserva a v2 e registra a única transição autorizada desta
etapa: a instalação APT de Xvfb e da introspecção GTK3, com `python3-gi`
preexistente. O relatório selado lista os 93 pacotes adicionados, versões,
hashes do histórico APT e do log dpkg e os hashes antes/depois de
`/var/lib/apt/extended_states` e `/var/lib/dpkg/status`. O gate da ISO aceita o
pack histórico somente quando sua referência e seu snapshot correspondem à
baseline v2; em paralelo, exige a transição v2→v3 exata e a correspondência do
host atual com a v3. Qualquer outra diferença continua bloqueada.

## Conteúdo da camada

A camada visual mantém a configuração estática do wallpaper DevLite nos quatro
monitores XFCE. Também substitui os aliases de tema Plymouth gráfico e textual
por um tema DevLite, e troca `LOGO=ubuntu-logo` por `LOGO=devlite` em
`/etc/os-release`; o ícone DevLite já existente é validado no Base. O
identificador técnico `ID=ubuntu` e os nomes de serviço/catálogo exigidos pela
compatibilidade não são alterados.

O overlay instala os arquivos com modo `0644`, links simbólicos esperados e
propriedade root no SquashFS. O gerador verifica formato, tamanho, conteúdo e
round-trip antes de incluir a camada nas cadeias `fsimage-layered` do Live e
do sistema instalado. O preflight rejeita overrides visuais no delta Live.

## Limite do Plymouth no Live

O `casper/initrd` de origem contém links e arquivos dos temas `xubuntu-logo` e
`xubuntu-text`. Esse initrd é preservado byte a byte pelo gerador ISO; uma
camada SquashFS não pode substituir arquivos usados antes de o rootfs Live ser
montado. Portanto, o tema DevLite vale para o rootfs em camadas e para a
instalação resultante, mas a tela de splash do initramfs Live permanece
Xubuntu até uma mudança separada e validada do initrd. O contrato e o relatório
registram essa pendência; boot e instalação permanecem `vm_tested: false`.

## DevControl e validação

O teste GTK sob Xvfb reproduziu e corrigiu o acesso incorreto ao `Gtk.Grid`
embalado pelo `Gtk.ScrolledWindow`. O teste de regressão instancia a aplicação,
confirma sua janela mapeada e a fecha. A execução adicional usa o coletor real;
os testes automatizados usam um snapshot fixo para não consultar o host.

O contrato v3 sela o código e a proveniência atuais, o pack aprovado, as duas
camadas, o wallpaper, os aliases Plymouth, o ícone, a ISO fonte e o orçamento
de espaço. A auditoria estrutural verifica hashes, manifestos, camada visual,
metadados de boot e preservação do initrd; não afirma boot ou instalação em
Hyper-V.
