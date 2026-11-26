# Continuação: armazenamento, Adminer, Control 2.0 e Modern

## Armazenamento — proposta, sem exclusões

Auditoria sem alterações de dados: inventário acessível e duas consultas privilegiadas apenas de nomes/tamanhos, previamente autorizadas. Os diretórios privados não foram abertos para leitura de conteúdo nesta etapa. Inventário: docs/evidencias/armazenamento-continuacao.json. Índices APT: 39 cópias com SHA-256 idêntico às canônicas, sem hardlinks, somando 1,012 GiB. Lista exata e hashes em docs/evidencias/indices-apt-duplicados-continuacao.json.

Proposta completa: docs/evidencias/limpeza-continuacao-proposta.json. Total estimado 8,351 GiB; não é garantia antes do preflight. Quatro candidatos maiores mais 39 arquivos individuais APT. Preservar todos os InRelease e os índices canônicos; para repetir planos históricos, restaurar os índices nos caminhos antigos a partir das cópias preservadas. SquashFS privados exigem comparação atual dos hashes com as cópias canônicas antes de autorização de execução. Conferir também mounts, loops, processos, hardlinks, symlinks e dependências dos contratos. Se qualquer validação falhar, excluir o item da operação, sem ampliar escopo.

Preservar todas as imagens ext4 Base/Live aceitas, ISO oficial, ISO homologada release-1hu5dx5v, ISO básica phase4b1, fontes, Git, caches .deb, manifests, assinaturas, hashes, relatórios e logs. Não remover diretórios de job inteiros. A ISO release-c0srssh8 é experimental antiga: sua exclusão perde essa cópia histórica; as fontes e receitas permanecem. O diretório result-iso-tree não faz parte da limpeza proposta.

## Preparação

Adminer: prototypes/adminer/README.md; wrapper PHP, política de acesso, VirtualHost dedicado, manifesto e harness PHP preparados. Não instalado. Upstream preservado sem nova cópia grande/download. Porta 8081 atualiza a proposta antiga de porta 80; referências históricas não são configuração de implantação.

Control: prototypes/control2/app.py continua protótipo GTK3 com backend simulado. Três serviços explícitos, start/stop/restart e enable/disable separados, confirmações, erros simulados, execução assíncrona e consulta de logs. Logs em memória agora limitados a 50 entradas. Link do Adminer aponta ao endpoint dedicado; botão continua simulado, sem abrir conexão ou executar serviço. O helper/policy propostos não foram instalados. Futuro helper deve validar lista fechada e argv, autorizar via Polkit, distinguir estado ativo de UnitFileState e tratar socket/aliases/dependências, sem root genérico ou sudo sem senha. Preservar Control homologado.

Modern: prototypes/devlite-modern/README.md e payload/ consolidam o rascunho já preparado. Sem aplicação às camadas. Perfil de usuário/primeira sessão/dconf/wallpaper real ainda requer adaptação e testes autorizados.

## Limitações

Testes Python simulam operações e verificam artefatos/configuração; não substituem PHP/Apache/MariaDB, renderização GTK, autenticação Polkit, navegador real ou boot/instalação da nova composição. Nenhuma nova ISO, instalação, alteração de serviço ou imagem nesta continuação. A sintaxe PHP 8.3 do arquivo upstream foi validada anteriormente; o novo wrapper e suas políticas ainda não foram executados em PHP.
