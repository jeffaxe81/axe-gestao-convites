# Quadro de fechamento — dez frentes técnicas da Isadora

Atualização: 09/11/2026. **Este quadro mede o desenvolvimento, não autorização para produção.** Cada gate técnico vale dez pontos. Somente marcar concluído quando código integrado e evidência CI válida existirem.

| Frente | Issue | Entrega verificável | Estado em 09/11/2026 |
| --- | --- | --- | --- |
| F1 — CI e regressões | #14 | pytest, Chromium/WebKit, MySQL, Compose e migrações | CI #310 aprovada; novo SHA da PR #13 aguarda #316 |
| F2 — Excel/CSV | #15 | modelo, importação idempotente e validação | PR #12 mesclada em `main` (be6490e) |
| F3 — Links por família | #16 | token individual, isolamento e privacidade | PR #12 mesclada; CI #303 verde |
| F4 — Dashboard | #17 | RSVP/envio/interesse independentes | PR #13, CI #316 em andamento |
| F5 — WhatsApp | #18 | compartilhamento preparado sem envio automático | PR #12 mesclada; CI #303 verde |
| F6 — Mobile | #19 | testes E2E de convite, RSVP e opt-in | PR #13, CI #316 em andamento |
| F7 — Cloudflare | #20 | documentação e testes de configuração | PR #22 em rascunho; CI #318 em andamento |
| F8 — Backup | #21 | testes de backup/restauração em Compose | CI #310 aprovada; operação real adiada |
| F9 — Integração | #23 | PRs #13/#22 + CI final de `main` | Pendente |
| F10 — Evidências / 90% | #24 | matriz de dez gates e acompanhamento | Este documento; gates pendentes ainda não pontuados |

## Dois percentuais diferentes

- **Técnico:** 10 gates de 10 pontos; meta mínima 9/10 comprovados. A evidência de CI deve ser do SHA final e PR mesclada quando assim exigido.
- **Operacional:** 6 de 7 etapas = **86%**, segundo a metodologia original. Só sobe com teste e aceite reais.

## Gates técnicos (status conservador)

| Gate | Pontuação | Justificativa |
| --- | ---: | --- |
| 1. Regras RSVP e prazo | 10 | PR #12 CI #303 verde e merge realizado |
| 2. MySQL, transações e migrações | 10 | PR #12 CI #303 verde; migrações 006 ainda dependem PR #13 |
| 3. Login/CSRF/sessão | 10 | PR #12 CI #303 verde |
| 4. Excel/CSV | 10 | PR #12 CI #303 verde e merge |
| 5. Links individuais | 10 | PR #12 CI #303 verde e merge |
| 6. WhatsApp manual | 10 | PR #12 CI #303 verde e merge |
| 7. Interesse voluntário | 0 | PR #13 não mesclada |
| 8. Dashboard + E2E | 0 | PR #13 não mesclada; CI #316 pendente |
| 9. Backup/Compose na versão final | 0 | CI do SHA final após os merges pendente |
| 10. Procedimentos Cloudflare integrados | 0 | PR #22 não mesclada |

**Progresso técnico conservador nesta medição: 60% (6/10)**. Esse número não é uma regressão da Release 1 e não substitui o 86% operacional: são métricas com denominadores e critérios diferentes.

## Condições de fechamento

- CI verde na revisão final da PR #13 e sem resultados de teste artificialmente declarados.
- Integrações sucessivas sem publicar automaticamente em `policorp`.
- Revisão da PR #22, cuja documentação está preparada mas ainda não implantada.
- CI e evidências do commit final da `main`.
- Registrar a meta técnica >=90% somente ao comprovar no mínimo nove gates.

## Homologação posterior, fora da meta técnica

Cloudflare Tunnel/HTTPS público real, backups externos com restauração no host, testes em Android/iPhone físicos, revisão de segurança e aceite operacional do organizador continuam obrigatórios para publicar convites reais.
