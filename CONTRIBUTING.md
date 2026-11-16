# Contribuição

Documentar decisões antes de implementar etapas de build. Não versionar ISOs, caches, imagens de VM, credenciais ou relatórios do host. Nunca incluir arquivos pessoais no overlay.

Verificação local: `python3 scripts/verificar-projeto.py`; `python3 scripts/diagnostico.py`; `git diff --check`.

A branch inicial é main. Preferir branches `feat/<tema>` e commits pequenos. O commit inicial pode ser feito com `git add README.md CONTRIBUTING.md .gitignore .gitattributes config packages overlay scripts pipeline tests docs assets sources/.gitkeep work/.gitkeep artifacts/.gitkeep reports/.gitkeep` e `git commit -m "docs: estrutura inicial do DevLite OS 1.0"`, após revisar `git diff --cached`.

Não configurar nome/e-mail automaticamente, não alterar configurações globais do Git e não publicar sem instrução. A licença do código original permanece pendente; licenças e marcas de terceiros devem ser preservadas e revisadas antes de distribuir.
