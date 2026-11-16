# Plano de desenvolvimento

| Fase | Entregas | Critério de saída |
|---|---|---|
| 1 — Planejamento | Estrutura, diagnósticos, arquitetura e critérios | Revisão dos documentos e dos recursos |
| 2 — Base e laboratório | Aprovação de download, autenticidade da ISO, inventário e VMs de teste | Base autenticada e live/instalador originais funcionando |
| 3 — Pipeline mínimo | Automação de extração e reconstrução sem customizações | ISO reconstruída inicia e instala em BIOS e UEFI |
| 4 — Software e idioma | Pacotes de desenvolvimento, redes, escritório e pt-BR | Ferramentas e idioma funcionam live e após instalação |
| 5 — Personalização | Arte original, menu XFCE e DevLite Control | Interface consistente e ações administrativas restritas |
| 6 — Qualidade e segurança | Auditoria de serviços, recursos, atualização e licenças | Matriz de aceitação aprovada e nenhuma falha crítica aberta |
| 7 — Release 1.0 | ISO, hashes, documentação de uso e recuperação | Instalação limpa reproduzida e entrega revisada |

Aprovações necessárias: baixar ISO e metadados; instalar dependências adicionais; executar operações privilegiadas na VM de build; iniciar cada construção; publicar artefatos. Alterações de disco ou partições permanecem fora do escopo sem autorização específica. Instalações de teste serão exclusivamente em discos virtuais descartáveis autorizados.
