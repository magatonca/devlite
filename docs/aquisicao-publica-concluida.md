# Aquisição e preparação pública concluídas

Somente os três arquivos autorizados foram baixados, como magaton, com retorno 0 e **44.127.998 bytes (42,08 MiB)** no total. Origem HTTPS exata, sem redirects; nenhum arquivo fora do plano foi adquirido.

| Arquivo | Bytes | SHA-256 |
|---|---:|---|
| node-v26.13.1-linux-x64.tar.xz | 34093052 | 5c063e46bab0fbc1c17cc445d7ff129cbdcd0471be6ed83b6ab864f8143bc864 |
| typescript-7.0.2.tgz | 365612 | da2513f4b95176d6dde8b51aab7afe8a927656c9d277369793f77f7e59371c08 |
| typescript-linux-x64-7.0.2.tgz | 9669334 | 7ecad6f67377e831856367ab062ef394f21506a611405bf8ac0ff039348637d3 |

Node: SHA-256 confere com os checksums OpenPGP autenticados anteriormente. TypeScript: os dois SHA-512/SRI conferem com os metadados cujas assinaturas ECDSA já foram verificadas. A autenticação prévia foi reutilizada; não houve novo download de chaves/metadados. Nenhuma versão foi atualizada.

Inspeção integral rejeitou paths perigosos, tipos especiais e permissões inesperadas. Arquivos internos confirmam TypeScript 7.0.2, sem scripts de lifecycle declarados, com provedor Linux x64 irmão do pacote principal. O launcher tsc chama JavaScript que seleciona o provedor nativo. Nenhum desses scripts ou binários foi executado.

Payload preparado em work/public-payload-rn0kd9ok: **254.929.023 bytes (243,12 MiB)** e **6.428 entradas**, incluindo identidade, menu XFCE, Control e entrada opcional de documentação do VS Code. Licenças e avisos upstream preservados. Trata-se de uma árvore de preparação, não uma alteração do hospedeiro ou da distribuição.

Auditoria readelf: Node e tsc nativo são ELF64 x86-64. Node requer glibc até 2.28, GLIBCXX até 3.4.21 e CXXABI até 1.3.11; libc6 2.39, libstdc++6/libgcc-s1/libatomic1 14.2 constam em ambas as visões publicadas. O tsc nativo não declarou bibliotecas dinâmicas nem interpretador ELF. Isso é compatibilidade estática; funcionamento real permanece pendente.

Concluído o adaptador de cópia aditiva auditada e preparado o controlador único de aplicação + reconciliação/empacotamento. **296 testes passaram**, incluindo 25 casos novos. Testes usam fixtures/mocks, sem mounts ou execução root. O controlador privilegiado novo ainda não foi executado.

Espaço livre: aproximadamente **70,78 GiB** após aquisição e staging. Hospedeiro íntegro, contrato anterior preservado e flags false. ISO original/experimental e imagens aceitas intactas; nenhuma nova ISO gerada.

Evidências: [aquisição](evidencias/aquisicao-publica-validada.json), [testes](../reports/testes-aplicacao-publica-preparada.txt). Próxima autorização: [aplicação e integração isoladas](autorizacao-aplicacao-publica.md).
