# Gerenciador de Convites da Isadora 🌼

Projeto para confirmação de presença no aniversário de **2 anos da Isadora**, dia **13/12/2026 às 15h** (America/Sao_Paulo). O local será configurado depois.

**Estado:** desenvolvimento iniciado. As regras de negócio foram implementadas e testadas; **o aplicativo ainda não recebe confirmações**.

## Progresso da release 1

`[██░░░░░░░░░░░░░░] 14% — 1/7 etapas verificadas`

O [andamento detalhado](docs/progresso.md) separa o que funciona daquilo que falta validar.

## Contagens

- 0–5 anos: lembrancinha, sem contar para o buffet.
- 6–12 anos: lembrancinha e buffet.
- Acima de 12 anos: buffet, sem lembrancinha infantil.
- Recusas: zero participantes.
- Limite de buffet 40: **alerta interno**, nunca regra pública de bloqueio.

## Rodar testes existentes

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests/unit/test_domain.py -q
```

Em 18/10/2026: **25 passed**, Python 3.13.5, pytest 9.0.2. Produção planejada com Python 3.12, Flask, MySQL e Docker (ainda sem validação).

## Planejamento

- [Especificação da release 1](docs/superpowers/specs/2026-10-18-isadora-release-1-design.md)
- [Plano de implementação](docs/superpowers/plans/2026-10-18-isadora-release-1.md)
- [Progresso](docs/progresso.md)

A página pública, domínio, hospedagem e envio do convite em PDF pelo WhatsApp ainda não estão disponíveis. Não versionar senhas nem dados reais de convidados.
