# Gerenciador de Convites da Isadora 🌼

Aniversário de dois anos da Isadora — 13/12/2026, 15h, America/Sao_Paulo. Local a confirmar.

**Estado: desenvolvimento (não disponível para convidados).**

## Barra de avanço verificado
`[███████░░░░░░░░░] 43% — 3 de 7 etapas com testes aprovados no CI`

Detalhes: [docs/progresso.md](docs/progresso.md).

### Implementado
- Regras de RSVP positivo/negativo, familiares e faixas de idade.
- 0–5 anos: lembrancinha, sem consumir buffet; 6–12: buffet e lembrancinha; acima de 12: buffet.
- Limite de 40 apenas para alerta interno; recusas não contam.
- Modelo de dados com UUID, revisão e idempotência; transações e segredo privado de edição.
- Migrations iniciais, ambiente Docker/Compose preparatório e teste MySQL para CI.

### Testes automatizados
```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
```
Em 18/10/2026: **49 testes aprovados no GitHub Actions**, incluindo teste de persistência com MySQL 8.4 real. Referência: https://github.com/jeffaxe81/axe-gestao-convites/actions/runs/39171820330. Testes manuais em dispositivos e Docker Compose completo ainda pendentes.

### Autenticação de organizadores
Os endpoints administrativos usam hash seguro de senha, sessão assinada e token CSRF.
Na instalação, defina `ORGANIZER_USERNAME`, `ORGANIZER_PASSWORD_HASH`
(gerado com `werkzeug.security.generate_password_hash`) e `SESSION_SECRET`.
O hash deve ficar entre aspas simples no `.env` por conter `# Gerenciador de Convites da Isadora 🌼

Aniversário de dois anos da Isadora — 13/12/2026, 15h, America/Sao_Paulo. Local a confirmar.

**Estado: desenvolvimento (não disponível para convidados).**

## Barra de avanço verificado
`[███████░░░░░░░░░] 43% — 3 de 7 etapas com testes aprovados no CI`

Detalhes: [docs/progresso.md](docs/progresso.md).

### Implementado
- Regras de RSVP positivo/negativo, familiares e faixas de idade.
- 0–5 anos: lembrancinha, sem consumir buffet; 6–12: buffet e lembrancinha; acima de 12: buffet.
- Limite de 40 apenas para alerta interno; recusas não contam.
- Modelo de dados com UUID, revisão e idempotência; transações e segredo privado de edição.
- Migrations iniciais, ambiente Docker/Compose preparatório e teste MySQL para CI.

### Testes automatizados
```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
```
Em 18/10/2026: **49 testes aprovados no GitHub Actions**, incluindo teste de persistência com MySQL 8.4 real. Referência: https://github.com/jeffaxe81/axe-gestao-convites/actions/runs/39171820330. Testes manuais em dispositivos e Docker Compose completo ainda pendentes.

.
Não usar senha em texto simples nem versionar o `.env`.

### Docker (em desenvolvimento, não liberar publicamente)
```bash
cp .env.example .env
# editar as quatro credenciais e segredos para valores aleatórios e fortes
docker compose up -d --build --wait
```
A API pública já está implementada; o painel autenticado e as interfaces ainda estão pendentes. **Não publicar a aplicação para convidados nesta etapa**.

### Planejamento
- [Especificação](docs/superpowers/specs/2026-10-18-isadora-release-1-design.md)
- [Plano](docs/superpowers/plans/2026-10-18-isadora-release-1.md)
- [Progresso](docs/progresso.md)

A interface pública, o painel, a hospedagem, o domínio e a distribuição do PDF/WhatsApp ainda não estão disponíveis. Não versionar credenciais nem nomes reais.
