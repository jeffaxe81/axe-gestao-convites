# Evolução do projeto — Gerenciador de Convites da Isadora

Atualizado em 18/10/2026. Percentual calculado por **etapas concluídas e testadas** (1 de 7 = 14%), não por horas previstas.

`[██░░░░░░░░░░░░░░] 14%`

| Etapa | Status | Evidência |
| --- | --- | --- |
| 1. Regras e prazo | Concluída localmente | 25 testes pytest aprovados (Python 3.13.5) |
| 2. MySQL e transações | Pendente | Sem integração executada |
| 3. API pública e edição | Pendente | Sem integração executada |
| 4. Autenticação e painel privado | Pendente | Sem integração executada |
| 5. Página mobile do convidado | Pendente | Sem testes em navegador |
| 6. Interface de organizadores | Pendente | Sem testes em navegador |
| 7. Docker, concorrência, CI e validação final | Pendente | Sem execução em Docker |

## Entregue agora

- Validação de respostas positivas e negativas, participantes, principal, nomes e idade.
- Faixas de idade 0–5, 6–12 e acima de 12, contagens de buffet e lembrancinhas.
- Edição sem prazo configurado ou encerramento no instante limite.
- 25 testes de unidade passando; nenhuma dependência de banco ou frontend na etapa 1.

## Ainda não validado

O aplicativo web, API, persistência, autenticação, Docker, concorrência, CI e testes mobile ainda não foram implementados nem validados. Não divulgar link de RSVP até completar essas etapas. A informação do buffet não poderá aparecer na página pública.

Referências: especificação e plano em docs/superpowers.
