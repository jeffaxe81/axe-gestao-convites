# Seis frentes de trabalho — Convites AXE

Data: 29/10/2026. Branch `feat/isadora-release-1`. PR #1 rascunho.

As frentes indicam seis áreas de implementação e verificação, não seis agentes humanos/autônomos. O desenvolvimento de código e a CI podem avançar sem credenciais de produção. **Progresso de liberação permanece 86% (6/7 etapas)**.

| Frente | Entrega técnica | Verificação |
| --- | --- | --- |
| 1 — Login e painel | Limpeza imediata da senha do formulário inclusive em falha de autenticação/rede | Testes Playwright |
| 2 — HTTPS e redirecionamentos | Verificador de produção bloqueia redirecionamento para HTTP/outra origem antes de seguir | Testes unitários do verificador |
| 3 — Pré-check DNS | Rejeita domínio inválido, porta alternativa e sufixos reservados | Testes Python |
| 4 — Backup e recuperação | Rejeita symlink e dump SQL com permissões públicas antes de restaurar | Testes de segurança + MySQL CI |
| 5 — PDF de convite | Opção `--check-production` consulta HTTPS e painel privado, sem alterar RSVP, antes do PDF definitivo | Testes simulados de aprovação/falha |
| 6 — Qualidade e CI | Análise sintática de Python e JavaScript, regressões e Docker/MySQL/restauração | Pipeline GitHub Actions |

## Limites da entrega

- CI usa banco e convidados sintéticos, não corresponde a teste no servidor final.
- Não houve publicação externa, envio de WhatsApp ou leitura de dados pessoais de convidados.
- Para chegar a 100%, comprovar domínio e TLS, controles do túnel/proxy, recuperação de backup no host real, testes PDF recebido via WhatsApp em Android e iPhone físicos, revisão de segurança e aceite operacional.

## Ordem de liberação

1. Preparar domínio e servidor. Não enviar senhas/tokens ao GitHub/chat.
2. Executar `python scripts/preflight.py --env-file .env` no host.
3. Executar `python scripts/check_production.py --url https://DOMINIO_REAL` a partir de rede externa.
4. Configurar e testar backup cifrado externo e restauração no servidor final.
5. Gerar PDF definitivo com `--check-production`, testar em dispositivos físicos e registrar resultados.
6. Solicitar aceite técnico; manter a PR em draft e o convite não distribuído até então.
