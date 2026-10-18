# Evolução do projeto — Gerenciador de Convites da Isadora

Data de referência: 18/10/2026.

**Barra de etapas verificadas** (cada uma vale 1/7): `[███████░░░░░░░░░] 43%`

| Etapa | Situação | Evidência |
| --- | --- | --- |
| 1. Regras e prazo | Concluída | Regras de idade/prazo cobertas nos testes |
| 2. MySQL e transações | Concluída na validação automatizada inicial | Integração MySQL real incluída no CI; concorrência de estresse reservada à etapa 7 |
| 3. API pública e edição | Concluída na validação automatizada inicial | HTTP com autenticação por token, revisão, idempotência, expiração, privacidade e health |
| 4. Autenticação e painel | Não iniciada | Pendente |
| 5. Página do convidado | Não iniciada | Pendente |
| 6. Interface dos organizadores | Não iniciada | Pendente |
| 7. Docker, testes E2E e operação | Preparação iniciada | Dockerfile, Compose e CI existentes; teste real do Compose e navegadores pendentes |

**Evidência automatizada:** 49 testes aprovados em Python 3.12 no GitHub Actions (MySQL 8.4), execução: https://github.com/jeffaxe81/axe-gestao-convites/actions/runs/39171820330.

**Limitações:** os testes HTTP atuais usam SQLite como fixture isolada; o teste de persistência dedicado exercita MySQL real. O Compose não foi exercitado integralmente e testes reais em Android/iPhone ainda não foram feitos. Ainda não divulgar link para convidados, pois faltam interfaces e painel autenticado.

**Critério do percentual:** etapas integralmente implementadas com a bateria automatizada inicial aprovada / 7, arredondadas. O trabalho de estresse, operação e dispositivos é contabilizado exclusivamente na etapa 7. Não transformar progresso técnico em alegação de liberação de produção.
