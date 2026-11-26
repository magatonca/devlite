# Segurança do navegador

**Reprovado na v5 real. Não executado na v6.** O teste isolado da v5 demonstrou HTML e JavaScript, mas a sessão XFCE/X11 real apresentou série de negações.

O perfil herdado usa `/att/devlite-epiphany` para o ensaio isolado e já inclui permissões para alguns binds de Bubblewrap em `/oldroot` e `/newroot`. A política de barramento de sessão também contém uma regra ampla de envio/recebimento. Isso exige mapear processos, transições e perfis da sessão real antes de alterar a política. A compilação do perfil v5 com apparmor_parser passou sem carregar política no host.

Reproduzir em XFCE/X11 com AppArmor enforce, D-Bus de sessão/sistema, Xauthority, áudio, acessibilidade e GTK. Capturar negações com etiquetas completas e correlacionar cada uma com o processo Epiphany, proxy D-Bus ou WebKit. Verificar registro do nome do aplicativo e consultas estritamente necessárias. Restringir configuração e mounts por caminho e destino. Tratar Xauthority como credencial e testar que processos WebKit não ganham acesso indevido a ela, SSH ou demais dados sensíveis. Comparar menu e navegador padrão, HTML, JavaScript, HTTPS, namespaces, seccomp e capabilities.

O host tem parser AppArmor e Xvfb, sem KVM, QEMU ou sessão XFCE/Xorg local disponíveis. Portanto a revisão de política para publicação continua pendente. Manter o navegador e o perfil publicados da v5 intactos. [AppArmor no Ubuntu](https://documentation.ubuntu.com/security/security-features/privilege-restriction/apparmor/)

## Perfil candidato v6

O perfil remove duplicatas e a regra genérica de envio/recebimento no barramento de sessão. Adiciona registro do nome Epiphany, interfaces de aplicação e acessibilidade, consultas pontuais no barramento de sistema, áudio e caminhos conhecidos de configuração. Mantém a autorização X11 via abstração oficial para o navegador e recusa leitura de Xauthority pelos caminhos de bind do sandbox. Se a inicialização depender desse bind, a compatibilidade precisará ser resolvida com evidência real e sem ampliar acesso à credencial. As regras herdadas de montagem e capacidades do Bubblewrap ainda exigem revisão dinâmica no Hyper-V. A compilação estática passou. O navegador permanece sem homologação.
