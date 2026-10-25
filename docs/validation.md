# Validação — Gerenciador de Convites da Isadora

## Situação atual — 25/10/2026

**Execução atual nesta sessão:** 137 testes aprovados, sem falhas ou skips, em 51,39 s; Python 3.12, MySQL 8.4 e Chromium. Três casos novos verificam duas edições simultâneas da mesma família, mudança concorrente do prazo e relógio cruzando o prazo durante espera por lock. O último caso falhou antes da correção e passou depois.

Ver [relatório de fechamento técnico](release-1-final-verification.md) para comandos, revisão independente por agente, evidências Docker/backup e pendências de homologação. A CI do novo commit precisa ser conferida depois do push.

### Evidência anterior — 23/10/2026

**Última execução integralmente aprovada:** https://github.com/jeffaxe81/axe-gestao-convites/actions/runs/40042632010

- **134 testes aprovados** (Python/Playwright), atualização manual/automática 15/30/60 s do painel, busca privada e reautenticação após expiração.
- Docker Compose e verificações de idempotência e persistência aprovados.
- Backup MySQL, restauração isolada, cifragem autenticada e restauração do arquivo decifrado aprovados no runner.
- Dois testes adicionais aprovaram a rejeição de HTTP 200 malformado e de contagem incoerente, preservando dados e filtros anteriores.
- **Permanece não comprovado:** operação real em domínio HTTPS, revisão independente, armazenamento externo operacional e teste físico Android/iPhone a partir do PDF/WhatsApp.

### Histórico de verificações


## Automatizado e comprovado em 18/10/2026

GitHub Actions: https://github.com/jeffaxe81/axe-gestao-convites/actions/runs/39175630043

- **84 testes aprovados** em Python 3.12, MySQL 8.4 e Chromium.
- Regras de RSVP, idades 0, 5, 6, 12, 13, recusa, prazo, idempotência e revisão.
- Testes de persistência em MySQL real e concorrência: 20 requisições com chave idêntica, 20 famílias diferentes; totais exatos.
- API pública, privacidade das famílias e do buffet, sessão administrativa e CSRF.
- Testes de cabeçalhos CSP, X-Frame-Options, Cache-Control, Referrer-Policy, proteção da URL HTTPS, porta HTTP ligada apenas em loopback.
- Testes de proxy: sem confiança explícita, X-Forwarded-For é ignorado; com um proxy confiável, o limitador distingue os visitantes.
- Headless Chromium: fluxo positivo, recusa, edição, nomes com HTML exibidos como texto, layout mobile; painel com login, contadores, alterações e logout.
- Docker Compose: imagem construída, MySQL/application saudáveis, envio repetido, login, configurações e recriação dos serviços com mesmo volume.
- Mensagem de smoke test registrada no CI: PASS: idempotency, RSVP token, MySQL volume and event settings survive recreation.

## Não executado nesta sessão

- Checklist físico Android e iPhone recebendo PDF com link via WhatsApp; ambos ainda sem validação.
- Homologação de domínio, HTTPS/TLS, proxy reverso, certificados e backup/restauração em hospedagem real.
- Auditoria independente de segurança, rate limiting global e procedimento de recuperação operacional.

Não criar um link público de convite nem marcar a Release 1 como pronta para produção sem aprovação desses pontos.

## Incremento operacional comprovado em 18/10/2026 (horário de Brasília)

Execução: https://github.com/jeffaxe81/axe-gestao-convites/actions/runs/39180698046

- **95 testes Python passaram** (14,33 s na etapa de testes).
- Docker Compose e testes de persistência aprovados.
- Backup SQL comprimido gerado em arquivo com permissão 0600 no runner, fora do repositório.
- Restauração realizada em banco temporário; comparação de event_settings, families e participants **idêntica** à origem.
- Banco restaurado temporário removido ao final, sem modificar o banco original.

**Não comprovado:** criptografia e armazenamento externo de backup, restauração em hospedagem real, auditoria independente, domínio/HTTPS ativo ou dispositivos físicos Android/iPhone. O script de inspeção pública HTTPS requer implantação real e não foi executado nesta CI.
