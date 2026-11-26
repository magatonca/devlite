# ISO pública candidata — controlador preparado

A aplicação e a integração autorizadas em `release-cezaiofx` são operações distintas da geração da ISO. A geração continua bloqueada até aprovação específica do comando e do contrato que serão preparados após a integração.

O controlador `scripts/gerar-iso-publica.py` prepara um contrato de geração única sem privilégios. Exige `public-result.json` root-owned com estado `public_layers_verified`, auditorias Base/Live aprovadas e recibo das camadas com comparação integral, round-trip SquashFS e composição pelo kernel aprovados. Vincula código, referências, ISO original, arquivos publicados e recibos por SHA-256. Não aceita uma execução de diagnóstico como aplicação.

A preparação não gera imagem. A execução exige aprovação explícita, usuário magaton, `PYTHONHASHSEED=0`, espaço suficiente e todos os gates persistentes desabilitados. Uma marca exclusiva impede duas execuções do mesmo contrato. Falhas preservam a tentativa, sem repetir a construção ou excluir artefatos.

A construção reutiliza o replay do boot híbrido do xorriso, preserva a EFI anexada e o instalador original, atualiza os checksums e arquiva as assinaturas originais sem apresentá-las como assinatura da imagem modificada. A auditoria compara árvores, metadados, checksums, BIOS/UEFI e EFI. O artefato só recebe o nome final após aprovação estrutural.

O perfil público inclui a proveniência de Node.js e TypeScript; VS Code permanece opcional, fora da ISO. A candidata não recebe aprovação de lançamento nem de boot/instalação sem testes práticos. Uma geração única também não comprova a reprodução bit a bit da candidata.

## Testes preparados

Foram executados 14 testes unitários adicionais, com backend simulado, em `reports/testes-preparacao-iso-publica.txt`. Eles verificam recibos inválidos, auditorias incompletas, adulteração, autorização específica, rejeição de root, execução única e preservação de falhas. Não geram ISO e não substituem a futura auditoria real.

## Próximo comando

Após o término aprovado da integração, executar apenas a preparação não privilegiada com `--prepare` e `--application-sha256`. Registrar o novo job, hash, orçamento de disco e comando de geração para autorização. Nenhum comando de geração está autorizado por este documento.
