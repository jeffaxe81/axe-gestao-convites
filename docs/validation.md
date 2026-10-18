# Evidências de validação da Release 1 — 18/10/2026

## Validado automaticamente

- GitHub Actions: https://github.com/jeffaxe81/axe-gestao-convites/actions/runs/39173412037
- Resultado: **69 testes aprovados** em Python 3.12.
- MySQL 8.4 no CI: cenário de transações e idempotência com banco real.
- Regras, persistência isolada, API, autenticação e checagens de privacidade HTTP.
- Chromium: confirmação positiva, recusa, edição pelo link privado, nomes renderizados como texto, layout mobile sem rolagem horizontal.
- Chromium: login dos organizadores, listas, totais, configuração do local/prazo, logout e login inválido.
- Código verificado: commit 13f9a1ba85adbe051b42e6d4d0e1917b810b710d.

## Ainda não comprovado

- Inicialização integral do Docker Compose com todos os serviços e dados em volume persistente.
- Teste intensivo de requisições concorrentes, indisponibilidade do banco e recuperação.
- Link aberto pelo PDF recebido em WhatsApp em dispositivos Android e iPhone reais.
- Configuração pública HTTPS/DNS e políticas de monitoração, backup e retenção.
- Revisão independente de segurança antes de aceitar dados reais.

Não declarar ambiente de produção liberado antes dessas verificações. Nenhuma hospedagem, domínio, senha ou credencial de produção foi provisionado.
