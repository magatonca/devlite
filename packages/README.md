# Seleção declarativa

`selection.json` organiza 47 itens nas categorias sistema, desenvolvimento, redes, escritório e interface, com dependências lógicas, providers e conflitos. `sources.json` descreve origens; as externas estão desabilitadas. Não passar o JSON diretamente ao apt: há itens Node, npm e Microsoft com mecanismos distintos.

Ver [lista completa e candidatos](../docs/pacotes-origens.md), [arquitetura](../docs/fase4a-personalizacao.md) e `config/customization-lock.json`, que continua não resolvido. A ferramenta `scripts/planejar-personalizacao.py` valida e exporta a preparação sem instalar nada.
