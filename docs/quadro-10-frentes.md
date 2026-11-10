# Quadro de fechamento — dez frentes técnicas da Isadora

**Data de referência:** 09/11/2026, após a integração das PRs #12, #13 e #22.

Nota metodológica: o percentual técnico abaixo decorre de evidências binárias de código, merge e CI para dez gates originalmente definidos em `docs/progresso.md`.

**Prontidão técnica para homologação: 100% (10/10 gates comprovados).**

**Liberação operacional: 86% (6/7 etapas).** O avanço técnico não autoriza envio de convites reais nem prova domínio HTTPS, aparelhos físicos ou restauração de backup no servidor final.

## Evidência-base

- `main` no SHA `bb3e91e842f026e2016f8d678b214df2ca59782b`.
- GitHub Actions CI [#42715610262](https://github.com/jeffaxe81/axe-gestao-convites/actions/runs/42715610262): **sucesso**; 315 testes Python/Chromium/WebKit aprovados; sintaxe Python/JS, um bilhão de operações de estado *sintéticas*, Compose/MySQL, persistência, backup, restauração descartável e cifragem verificados.
- PR [#12](https://github.com/jeffaxe81/axe-gestao-convites/pull/12) integrada: Excel/CSV, links individuais, WhatsApp manual e painéis.
- PR [#13](https://github.com/jeffaxe81/axe-gestao-convites/pull/13) integrada: interesse voluntário e métricas.
- PR [#22](https://github.com/jeffaxe81/axe-gestao-convites/pull/22) integrada: procedimentos Cloudflare Tunnel/Policorp e verificação não destrutiva.

## Dez gates — critérios técnicos cumpridos

| Gate | Frente | Evidência no SHA auditado | Pontos |
| --- | --- | --- | ---: |
| 1 | RSVP, edição e prazo (#14) | CI 315 testes; API e E2E | 10 |
| 2 | Persistência, migrações e idempotência (#14) | MySQL/Compose e migrações 001–006 na CI | 10 |
| 3 | Login, sessão e CSRF (#14) | Testes de acesso administrativo, logout e segurança | 10 |
| 4 | Excel/CSV (#15) | PR #12 e testes de importação/idempotência | 10 |
| 5 | Links familiares (#16) | PR #12 e testes de isolamento de token | 10 |
| 6 | Distribuição manual (#18) | PR #12, testes de WhatsApp preparado e registros reversíveis | 10 |
| 7 | Interesse voluntário (#17/#19) | PR #13 e testes de opt-in sem tracking passivo | 10 |
| 8 | Dashboard e E2E (#17/#19) | PR #13, Chromium/WebKit e contadores independentes | 10 |
| 9 | Backup, restore e Compose (#21) | CI #42715610262 com restaurações descartáveis | 10 |
| 10 | Publicação tecnicamente preparada (#20/#23) | PR #22 integrada, procedimentos Cloudflare, smoke e rollback documentados | 10 |
| **Total** | | **10/10 gates técnicos** | **100** |

## Acompanhamento das dez frentes

As issues #14–#21 e #23–#24 são rastreadores de atividades. **Este quadro avalia exclusivamente o critério técnico**, sem fechá-las automaticamente: se uma issue exige aceite físico, teste externo ou implantação, permanece aberta até essa evidência real.

## Ainda não homologado / não executado

- DNS/HTTPS e Cloudflare Tunnel no domínio `isadora2anos.org` vistos do mundo externo.
- Implantação definitiva do código novo no servidor `policorp`, com rollback ensaiado.
- Android e iPhone físicos, recebimento e uso dos convites reais.
- Backup cifrado externo e restauração testada no ambiente definitivo.
- Revisão independente de segurança, aceite do organizador e autorização de publicação.

**Diferença essencial:** CI verde significa que o código daquele commit passou a suíte automatizada. Não significa que o serviço em produção esteja atualizado. Não usar o percentual técnico para divulgar convites reais antes da etapa operacional restante.

## Incrementos posteriores

A PR #25 de relatório CSV/filtros, se ainda aberta, constitui evolução posterior à fotografia deste quadro. Sua validação deve ser apurada pelo próprio SHA e não altera retroativamente a evidência da `main` acima.
