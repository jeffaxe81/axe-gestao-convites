# Evolução — gerenciador de convites da Isadora

Referência: 18/10/2026.

**Barra de etapas finalizadas:** [██████████████░░] 86% — 6 de 7 etapas integralmente aprovadas.

| Etapa | Situação | Evidência |
| --- | --- | --- |
| 1. Regras e prazo | Concluída | Testes de idade, presença e prazo |
| 2. MySQL e transações | Concluída | MySQL 8.4, idempotência e migração |
| 3. API pública e edição | Concluída | Tokens, privacidade e revisão |
| 4. Acesso privado | Concluída | Sessões, CSRF e totais |
| 5. Interface pública | Concluída | Chromium mobile com confirmação, recusa e edição |
| 6. Interface dos organizadores | Concluída | Chromium com login, listas, configuração e logout |
| 7. Operação final | Parcialmente validada | 71 testes, concorrência com 20 requisições, Compose e persistência OK; checklist em Android/iPhone e revisão de segurança pendentes |

**Evidência operacional:** https://github.com/jeffaxe81/axe-gestao-convites/actions/runs/39174083670
- 71 testes passaram.
- Docker Compose construiu/subiu os serviços com MySQL em volume.
- Confirmação repetida não duplicou registros; token permaneceu válido após recriação dos serviços.
- Configuração do local e contadores preservados após reinício com o mesmo volume.

**Ainda pendente:** testes manuais Android e iPhone abrindo o link vindo de PDF/WhatsApp, revisão de configuração pública HTTPS e revisão final de segurança. Não declarar produção liberada.

**Regra de porcentagem:** etapas concluídas / 7, arredondadas. Enquanto a última etapa tiver pendências obrigatórias, o total permanece em 86%.

**Evento:** 13/12/2026 às 15h, America/Sao_Paulo, local configurável; contagem de buffet só interna, 40 como alerta, não bloqueio. O aplicativo não cria nem distribui o PDF do convite.
