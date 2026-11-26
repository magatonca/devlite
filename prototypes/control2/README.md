# DevLite Control 2.0 — protótipo isolado

O aplicativo atual e o backend administrativo não são substituídos. Nenhum comando systemctl, journalctl, pkexec, sudo ou consulta do host é executado pelo protótipo. O backend é exclusivamente SimulatedBackend; não há flag para ativar backend real.

Abrir `preview.html` em qualquer navegador: prévia estática autocontida, com controles inertes e dados fictícios. A página não é screenshot de GTK. Simulação interativa em uma sessão gráfica, sem root:

```bash
python3 /home/magaton/DevLite-OS/prototypes/control2/app.py
```

Checar apenas os bindings, sem janela, consulta do host ou serviços:

```bash
python3 /home/magaton/DevLite-OS/prototypes/control2/app.py --check
```

Serviços e informações são fictícios. Parar/reiniciar/desativar autostart exige confirmação no mock; habilitar boot não inicia serviço, desabilitar não para. Falhas podem ser injetadas pelos testes via next_error/unavailable, sem mudar serviços reais. Uma fila de trabalho serial evita bloquear a UI nas operações simuladas e impede duas ações simultâneas. GTK só é importado ao iniciar main; o modelo pode ser testado sem display.

`admin_argv()` documenta o futuro protocolo como vetor fixo, mas não executa nada. `policy-proposal.xml` é somente proposta, com autenticação administrativa explícita; não existe helper Control 2.0 instalado. O protótipo não monitora em background e encerra ao fechar a janela. A política de máscaras/boot real, tratamento de unit states transitórios e adaptação Base/Live ainda precisam ser implementados e aprovados.

Plano técnico e critérios de integração: `docs/devlite-control2-plano.md`.

Adminer: opção “Gerenciar bancos de dados” no mock apenas mostra a URL prevista quando Apache/MariaDB simulados estão ativos. Não abre navegador nem inicia serviços. Versão do pacote bloqueada por revisão de segurança. Planejamento e testes em `adminer_plan.py`, `adminer_model.py` e `docs/devlite-control2-adminer.md`; nenhum wrapper PHP foi instalado ou implementado.
