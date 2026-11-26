# Matriz de aceitação futura

A autenticidade da base foi aprovada na Fase 2. Os testes de execução e da futura distribuição permanecem **pendentes**. A reconstrução experimental da Fase 3B foi validada estruturalmente, com os testes manuais adiados por decisão do usuário. A preparação BIOS/UEFI da Fase 3A está em [procedimento específico](../docs/fase3a-testes-iso.md).

| Área | Ensaio e resultado esperado |
|---|---|
| Base | Assinatura oficial válida e SHA-256 confere |
| Boot | Live inicia em BIOS e UEFI em discos virtuais independentes; registrar configuração VMware |
| Secure Boot | Ensaiar separadamente; não anunciar compatibilidade sem aprovação do teste |
| Instalador | Instalação offline, quando suportada pela base, e online em discos descartáveis; reinício sem ISO |
| Localização | XFCE, menus e aplicativos em pt-BR; UTF-8, acentos e teclado br; testar após instalar |
| Desenvolvimento | PHP/Composer/Node/tsc/Git/gh/code executam; projeto PHP e TypeScript mínimos funcionam |
| Serviços | Ativação explícita Apache/MariaDB; HTTP local e consulta SQL; estados iniciais corretos |
| Containers | Compose v2 sobe e remove exemplo local após ativação autorizada; permissão de usuário revisada |
| Redes | Ferramentas abrem; captura autorizada em laboratório; Remmina e SSH em destino de teste; importação OpenVPN via NetworkManager |
| Escritório | Criar/salvar/reabrir documento, planilha e apresentação; abrir PDF |
| Segurança | Sem credenciais/identidades do host; portas e grupos conferem com política; autenticação do Control funciona e comandos arbitrários são recusados |
| Sistema | Atualização APT, dependências íntegras, DNS, rede VMware e reboot sem falhas críticas |
| Recursos | Registrar ISO, espaço instalado, pico de build, tempo e memória idle/carga em VM 2 vCPU/4 GiB |
| Entrega | Hashes finais conferem; manifest e licenças presentes; instalação independente reproduz resultado |

Cada execução deve registrar data, hash da ISO, versão do VMware, CPU/RAM/firmware/disco virtual, passos, resultado e evidência sanitizada. Falhas bloqueantes devem ser corrigidas e retestadas antes da release.
