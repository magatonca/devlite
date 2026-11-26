# Overlay futuro

Arquivos do sistema serão criados do zero e revisados antes de inclusão. Separar padrões do usuário em /etc/skel, configurações do sistema e recursos em /usr/share. Não copiar o home do construtor. Validar aplicação das configurações no live e no sistema instalado.

Na Fase 4A, configurações são geradas a partir de config/customization.json por pipeline/devlite/customize/settings.py. A exportação fica exclusivamente em work/phase4a-*/overlay; nenhum arquivo é aplicado ao sistema ou às camadas. UID/GID futuros são registrados no manifest sem operação privilegiada.
