# Evolução do projeto — Gerenciador de Convites da Isadora

Data de referência: 18/10/2026.

**Barra de etapas verificadas** (cada uma vale 1/7): `[██░░░░░░░░░░░░░░] 14%`

| Etapa | Situação | Evidência |
| --- | --- | --- |
| 1. Regras e prazo | Concluída | 25 testes locais passando |
| 2. MySQL e transações | Implementação inicial, validação incompleta | 10 testes com SQLite aprovados; MySQL real aguarda CI |
| 3. API pública e edição | Não iniciada | Aguardando |
| 4. Autenticação e painel | Não iniciada | Aguardando |
| 5. Página do convidado | Não iniciada | Aguardando |
| 6. Interface dos organizadores | Não iniciada | Aguardando |
| 7. Docker, testes E2E e operação | Preparação iniciada | Compose criado mas não testado |

Total local: **35 testes passando, 1 teste MySQL ignorado por ausência de banco**. Docker não estava disponível no ambiente de desenvolvimento local. O aplicativo web ainda não está pronto, portanto não divulgar link de RSVP.

Os artefatos de Docker nesta etapa são preparatórios: o aplicativo Flask e o entrypoint `wsgi.py` serão criados na etapa de API.
