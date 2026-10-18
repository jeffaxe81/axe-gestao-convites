# Evolução — gerenciador de convites da Isadora

Referência: 18/10/2026.

**Barra de progresso verificado:** [██████████████░░] 86% — 6 de 7 etapas concluídas em testes automatizados.

| Etapa | Situação | Evidência |
| --- | --- | --- |
| 1. Regras e prazo | Concluída | Testes de idade, presença e prazo |
| 2. Banco MySQL e transações | Concluída nos testes iniciais | Persistência com MySQL real no CI; estresse completo na etapa 7 |
| 3. API pública e edição | Concluída | HTTP, idempotência, tokens, revisão e privacidade |
| 4. Autenticação e painel de dados | Concluída | Hash de senha, sessão, CSRF, listas e configuração |
| 5. Interface do convidado | Concluída nos testes Chromium | Presença, recusa, acompanhantes, edição, XSS e layout mobile |
| 6. Interface dos organizadores | Concluída nos testes Chromium | Login, listas, contadores, local/prazo e logout |
| 7. Operação e ensaios finais | Pendente | Concorrência, Docker Compose, persistência e checklist Android/iPhone |

**Evidência:** 69 testes passaram no GitHub Actions (Python 3.12, MySQL 8.4 e Chromium): https://github.com/jeffaxe81/axe-gestao-convites/actions/runs/39173412037

**Pendências:** Docker Compose ainda não validado de ponta a ponta, concorrência extensiva, ensaio de recuperação e checklist real Android/iPhone. Não confundir Chromium automatizado com testes físicos de aparelhos. Domínio e hospedagem HTTPS também pendentes.

**Percentual:** etapas aprovadas / 7, arredondado. Concluir a última etapa exige validações objetivas, não apenas código enviado.

**Escopo:** aniversário da Isadora em 13/12/2026 às 15h, America/Sao_Paulo. Local configurável; contadores e limite de buffet estritamente internos. PDF e WhatsApp não integram esta release.
