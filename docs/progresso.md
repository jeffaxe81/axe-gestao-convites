# Evolução — gerenciador de convites da Isadora

Referência: 29/10/2026.

**Barra de etapas finalizadas:** [██████████████░░] 86% — 6 de 7 etapas integralmente aprovadas.

| Etapa | Situação | Evidência |
| --- | --- | --- |
| 1. Regras e prazo | Concluída | Testes de idade, presença e prazo |
| 2. MySQL e transações | Concluída | MySQL 8.4, idempotência e migração |
| 3. API pública e edição | Concluída | Tokens, privacidade e revisão |
| 4. Acesso privado | Concluída | Sessões, CSRF e totais |
| 5. Interface pública | Concluída | Chromium mobile com confirmação, recusa e edição |
| 6. Interface dos organizadores | Concluída | Chromium com login, listas, configuração e logout |
| 7. Operação final | Parcialmente validada | 152 testes na CI de 29/10/2026; concorrência com 20 requisições, Compose, persistência, backup com restauração e criptografia verificados; revisão de código independente realizada; aparelhos físicos, HTTPS definitivo e aceite operacional pendentes |

**Evidência operacional mais recente:** https://github.com/jeffaxe81/axe-gestao-convites/actions/runs/40909637407
- 152 testes passaram, incluindo CSP, X-Frame-Options, HTTPS obrigatório fora do localhost, proxy explicitamente confiável, painel pesquisável e atualização manual/automática.
- Validação do painel contra respostas inconsistentes, concorrência no fechamento de edições e gerador offline de PDF com botão/QR Code HTTPS aprovados.
- Docker Compose construiu/subiu os serviços com MySQL em volume.
- Confirmação repetida não duplicou registros; token permaneceu válido após recriação dos serviços.
- Configuração do local e contadores preservados após reinício com o mesmo volume.
- Criptografia AES-256-GCM, comparação criptográfica e restauração de dump decifrado verificadas em CI; não equivalem a restauração de produção.

**Incrementos operacionais incluídos em 18/10/2026:** scripts/backup_mysql.py (dump MySQL com acesso restrito + restauração em banco temporário com comparação de dados), scripts/check_production.py (verificações HTTPS sem gravação) e testes das validações de entrada. A CI de 18/10/2026 foi aprovada e comprovou backup MySQL e restauração em banco isolado; o teste de HTTPS público exige hospedagem real. Documentos: docs/backup-restore.md e docs/https-deployment.md.

**Revisão técnica de 25/10/2026:** análise de código por outro agente encontrou uma falha no prazo durante espera por locks MySQL. Regressão reproduzida (HTTP 200 indevido), corrigida e validada; ver [relatório de fechamento](release-1-final-verification.md). Essa revisão não representa auditoria externa de segurança.

**Ainda pendente:** domínio real e publicação via proxy HTTPS ou Cloudflare Tunnel, teste manual Android e iPhone abrindo link do PDF recebido via WhatsApp, armazenamento externo e restauração de backup em host real e auditoria externa de segurança. Não declarar produção liberada.

**Regra de porcentagem:** etapas concluídas / 7, arredondadas. Enquanto a última etapa tiver pendências obrigatórias, o total permanece em 86%.

**Evento:** 13/12/2026 às 15h, America/Sao_Paulo, local configurável; contagem de buffet só interna, 40 como alerta, não bloqueio. O gerador offline cria PDF com QR Code e botão HTTPS; o aplicativo não distribui o PDF nem envia WhatsApp.
