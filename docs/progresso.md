# Evolução — gerenciador de convites da Isadora

Referência: 08/11/2026.

**Barra de etapas finalizadas:** [██████████████░░] 86% — 6 de 7 etapas integralmente aprovadas.

| Etapa | Situação | Evidência |
| --- | --- | --- |
| 1. Regras e prazo | Concluída | Testes de idade, presença e prazo |
| 2. MySQL e transações | Concluída | MySQL 8.4, idempotência e migração |
| 3. API pública e edição | Concluída | Tokens, privacidade e revisão |
| 4. Acesso privado | Concluída | Sessões, CSRF e totais |
| 5. Interface pública | Concluída | Chromium mobile com confirmação, recusa e edição |
| 6. Interface dos organizadores | Concluída | Chromium com login, listas, configuração e logout |
| 7. Operação final | Parcialmente validada | 185 testes na CI de 29/10/2026; concorrência com 20 requisições, Compose, persistência, backup com restauração e criptografia verificados; revisão de código independente realizada; aparelhos físicos, HTTPS definitivo e aceite operacional pendentes |

**Última CI integral aprovada anterior à antecipação de novembro:** https://github.com/jeffaxe81/axe-gestao-convites/actions/runs/40945029136
- 185 testes passaram, incluindo CSP, X-Frame-Options, HTTPS obrigatório fora do localhost, proxy explicitamente confiável, painel pesquisável e atualização manual/automática.
- Validação do painel contra respostas inconsistentes, concorrência no fechamento de edições e gerador offline de PDF com botão/QR Code HTTPS aprovados.
- Sessão expirada durante configurações ou exportação e falha de logout tratadas com limpeza imediata de nomes, métricas e campos, verificadas em quatro novos testes E2E.
- Docker Compose construiu/subiu os serviços com MySQL em volume.
- Confirmação repetida não duplicou registros; token permaneceu válido após recriação dos serviços.
- Configuração do local e contadores preservados após reinício com o mesmo volume.
- Criptografia AES-256-GCM, comparação criptográfica e restauração de dump decifrado verificadas em CI; não equivalem a restauração de produção.

**Incrementos operacionais incluídos em 18/10/2026:** scripts/backup_mysql.py (dump MySQL com acesso restrito + restauração em banco temporário com comparação de dados), scripts/check_production.py (verificações HTTPS sem gravação) e testes das validações de entrada. A CI de 18/10/2026 foi aprovada e comprovou backup MySQL e restauração em banco isolado; o teste de HTTPS público exige hospedagem real. Documentos: docs/backup-restore.md e docs/https-deployment.md.

**Revisão técnica de 25/10/2026:** análise de código por outro agente encontrou uma falha no prazo durante espera por locks MySQL. Regressão reproduzida (HTTP 200 indevido), corrigida e validada; ver [relatório de fechamento](release-1-final-verification.md). Essa revisão não representa auditoria externa de segurança.

**Ainda pendente:** domínio real e publicação via proxy HTTPS ou Cloudflare Tunnel, teste manual Android e iPhone abrindo link do PDF recebido via WhatsApp, armazenamento externo e restauração de backup em host real e auditoria externa de segurança. Não declarar produção liberada.

**Regra de porcentagem:** etapas concluídas / 7, arredondadas. Enquanto a última etapa tiver pendências obrigatórias, o total permanece em 86%.

**Evento:** 13/12/2026 às 15h, America/Sao_Paulo, local configurável; contagem de buffet só interna, 40 como alerta, não bloqueio. O gerador offline cria PDF com QR Code e botão HTTPS; o aplicativo não distribui o PDF nem envia WhatsApp.

## Antecipação adicional de dois meses (08/11/2026)

Código implementado: histórico transacional sem PII, migração aditiva 002, CSV quantitativo de buffet, impressão privada com filtro, comparação da quarta tabela no restore, testes de API e navegador. Ver [plano e evidências](antecipacao-2-meses.md).

A última CI **confirmada** antes desta rodada era a execução 40945029136, com **185 testes aprovados**. Não aumentar os 86% enquanto faltarem a homologação real, os dispositivos físicos e o aceite operacional.

## Rodada de 20 melhorias — 08/11/2026

Código e testes das 20 melhorias registrados na branch: [inventário com critérios](entregas-20-melhorias.md). Domínio HTTPS real, Android/iPhone físicos, backup externo e aceite continuam pendentes. A etapa 7 continua aberta e a porcentagem permanece em 86%, mesmo com melhorias de produto aprovadas em CI.
