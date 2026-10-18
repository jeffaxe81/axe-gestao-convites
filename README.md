# Gerenciador de Convites da Isadora 🌼

Aniversário de dois anos da Isadora — 13/12/2026, 15h, America/Sao_Paulo. Local a confirmar.

**Estado: desenvolvimento (não disponível para convidados).**

## Barra de avanço verificado
`[██░░░░░░░░░░░░░░] 14% — 1 de 7 etapas completas`

Detalhes: [docs/progresso.md](docs/progresso.md).

### Implementado
- Regras de RSVP positivo/negativo, familiares e faixas de idade.
- 0–5 anos: lembrancinha, sem consumir buffet; 6–12: buffet e lembrancinha; acima de 12: buffet.
- Limite de 40 apenas para alerta interno; recusas não contam.
- Modelo de dados com UUID, revisão e idempotência; transações e segredo privado de edição.
- Migrations iniciais, ambiente Docker/Compose preparatório e teste MySQL para CI.

### Testes locais
```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
```
Em 18/10/2026: **35 passaram e 1 teste foi ignorado** porque não havia MySQL acessível. A integração com banco real é testada pelo workflow do GitHub Actions, quando executado.

### Docker (ainda não operacional)
```bash
cp .env.example .env
# editar as quatro credenciais e segredos para valores aleatórios e fortes
docker compose up -d --build --wait
```
A API Flask ainda será implementada; **não executar como ambiente real nesta etapa**.

### Planejamento
- [Especificação](docs/superpowers/specs/2026-10-18-isadora-release-1-design.md)
- [Plano](docs/superpowers/plans/2026-10-18-isadora-release-1.md)
- [Progresso](docs/progresso.md)

Página pública, hospedagem, domínio e distribuição de PDF/WhatsApp ainda não disponíveis. Não versionar credenciais nem nomes reais.
