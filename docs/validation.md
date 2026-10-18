# Validação — Gerenciador de Convites da Isadora

## Automatizado e comprovado em 18/10/2026

GitHub Actions: https://github.com/jeffaxe81/axe-gestao-convites/actions/runs/39174083670

- **71 testes aprovados** em Python 3.12, MySQL 8.4 e Chromium.
- Regras de RSVP, idades 0, 5, 6, 12, 13, recusa, prazo, idempotência e revisão.
- Testes de persistência em MySQL real e concorrência: 20 requisições com chave idêntica, 20 famílias diferentes; totais exatos.
- API pública, privacidade das famílias e do buffet, sessão administrativa e CSRF.
- Headless Chromium: fluxo positivo, recusa, edição, nomes com HTML exibidos como texto, layout mobile; painel com login, contadores, alterações e logout.
- Docker Compose: imagem construída, MySQL/application saudáveis, envio repetido, login, configurações e recriação dos serviços com mesmo volume.
- Mensagem de smoke test registrada no CI: PASS: idempotency, RSVP token, MySQL volume and event settings survive recreation.

## Não executado nesta sessão

- Checklist físico Android e iPhone recebendo PDF com link via WhatsApp; ambos ainda sem validação.
- Homologação de domínio, HTTPS/TLS, proxy reverso, certificados e backup/restauração em hospedagem real.
- Auditoria independente de segurança, rate limiting global e procedimento de recuperação operacional.

Não criar um link público de convite nem marcar a Release 1 como pronta para produção sem aprovação desses pontos.
