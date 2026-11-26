"""Seleção declarativa com dependências lógicas; não substitui resolver APT."""
import re

CATEGORIES = {'sistema', 'desenvolvimento', 'redes', 'escritorio', 'interface'}
PROVIDERS = {'ubuntu', 'node-upstream', 'npm-upstream', 'microsoft-vscode'}
NAME = re.compile(r'[a-z0-9][a-z0-9+.-]*')


class SpecError(ValueError):
    pass


def resolve(spec, categories=None):
    if not isinstance(spec, dict):
        raise SpecError('Manifest deve ser objeto JSON')
    forbidden = spec.get('forbidden_apt')
    if not isinstance(forbidden, list) or any(not isinstance(x, str) or not NAME.fullmatch(x) for x in forbidden):
        raise SpecError('Lista de providers APT proibidos inválida')
    if not {'nodejs', 'npm', 'node-typescript', 'docker-ce', 'docker-ce-cli', 'containerd.io', 'docker-compose-plugin'} <= set(forbidden):
        raise SpecError('Política de conflito Node/Docker incompleta')
    if spec.get('schema') != 1 or spec.get('suite') != 'noble' or spec.get('architecture') != 'amd64':
        raise SpecError('Esquema/base/arquitetura não suportados')
    groups = spec.get('categories')
    if not isinstance(groups, dict) or set(groups) != CATEGORIES:
        raise SpecError('Declarar exatamente as cinco categorias previstas')
    index = {}
    package_keys = set()
    for category, items in groups.items():
        if not isinstance(items, list):
            raise SpecError('Categoria deve conter lista')
        for item in items:
            if not isinstance(item, dict):
                raise SpecError('Entrada de pacote inválida')
            key = item.get('id')
            package = item.get('package')
            if not isinstance(key, str) or not NAME.fullmatch(key) or key in index:
                raise SpecError('ID inválido ou duplicado')
            if not isinstance(package, str) or not NAME.fullmatch(package):
                raise SpecError(f'Nome de pacote inválido: {key}')
            if item.get('provider') not in PROVIDERS or item.get('scope') != 'installed-and-live':
                raise SpecError(f'Origem ou escopo inválido: {key}')
            if not isinstance(item.get('depends_on'), list) or any(not isinstance(x, str) for x in item['depends_on']):
                raise SpecError(f'Dependências inválidas: {key}')
            if item['provider'] == 'ubuntu' and package in spec.get('forbidden_apt', []):
                raise SpecError(f'Provider APT conflitante: {package}')
            pair = (item['provider'], package)
            if pair in package_keys:
                raise SpecError(f'Pacote duplicado: {package}')
            package_keys.add(pair)
            index[key] = dict(item, category=category)
    for key, item in index.items():
        if any(dependency not in index for dependency in item['depends_on']):
            raise SpecError(f'Dependência inexistente: {key}')
    chosen = set(categories) if categories is not None else CATEGORIES
    if not chosen or chosen - CATEGORIES:
        raise SpecError('Categorias selecionadas inválidas')
    ordered, visiting, visited = [], set(), set()
    def visit(key):
        if key in visiting:
            raise SpecError(f'Ciclo de dependências: {key}')
        if key in visited:
            return
        visiting.add(key)
        for dependency in sorted(index[key]['depends_on']):
            visit(dependency)
        visiting.remove(key)
        visited.add(key)
        ordered.append(index[key])
    # Verifica ciclos inclusive em categorias desmarcadas.
    for key in sorted(index):
        visit(key)
    ordered.clear(); visited.clear()
    for key in sorted(index):
        if index[key]['category'] in chosen:
            visit(key)
    return ordered
