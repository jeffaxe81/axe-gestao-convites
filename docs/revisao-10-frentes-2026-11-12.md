# Rodada de dez frentes — continuidade técnica da Release 1

Referência: 12/11/2026. Esta matriz organiza dez análises de engenharia
executadas sobre o código do repositório. **Não** representa dez revisores
humanos independentes, auditoria externa nem execução no host `policorp`.

**Objetivo:** melhorar segurança e preparo para homologação, mantendo
100% dos dez critérios técnicos já documentados e 86% operacional (6/7).
**Meta solicitada de 95% operacional: ainda não demonstrada.**

| Frente | Verificação de código | Resultado desta rodada |
|---|---|---|
| F1 Segurança de perímetro | `app/security.py` | Limitar cardinalidade por IP a 20 mil buckets por worker, sem varredura ampla ao atingir o teto |
| F2 Autenticação | `app/organizer.py`, `app/__init__.py` | O mesmo limiter atende tentativas de login; exige validação externa de WAF |
| F3 Convites individuais | `app/public.py`, `app/rsvp.py` | Fluxo exige token em produção; teste em família fictícia ainda necessário |
| F4 Importação | `app/guest_list.py`, `app/guest_xlsx.py` | Prévia valida Excel/CSV sem gravar; amostras físicas de dados devem ser fictícias |
| F5 Painel | `app/organizer.py`, `app/reports.py` | Dados privados permanecem atrás de sessão; verificar fluxos de campo |
| F6 Experiência móvel | `app/static/guest.js` | Cobertura emulada existente, porém Android/iPhone reais pendentes |
| F7 Distribuição | `app/static/admin.js` | WhatsApp assistido/manual; **não** há prova de entrega ou envio automático |
| F8 Backup e privacidade | `scripts/backup_mysql.py` | Mensagens de falhas deixam de repetir stderr potencialmente sensível; restauração final pendente |
| F9 Publicação | `scripts/check_production.py`, `scripts/check_deployed_revision.py` | Diagnósticos somente leitura disponíveis; DNS/TLS externos e SHA no servidor pendentes |
| F10 CI e aceite | `scripts/check_green_main_ci.py`, `scripts/release_readiness.py` | Gate da CI e evidências separados; CI pós-merge do novo SHA ainda deve ser confirmada |

## Evidências de código desta rodada

- Proteção do limitador por janela com capacidade de IPs limitada e testes de
  saturação, expiração, concorrência e uso desabilitado.
- O dump e as comparações de backup deixam de incluir stderr cru
  na exceção, reduzindo vazamento de credenciais e informações internas.
- Os testes simulam stderr contendo segredos e dados fictícios e verificam
  que falhas descartam arquivos incompletos.

## O que falta para homologação operacional

1. Diagnóstico e prova externa de DNS/HTTPS/Cloudflare Tunnel;
2. Backup cifrado externo com restauração isolada no host definitivo;
3. Testes de link/PDF/RSVP em Android físico;
4. O mesmo ensaio, incluindo instabilidade, em iPhone físico;
5. Revisão independente de segurança, com tratamento de achados;
6. Aceite expresso do organizador posterior aos cinco itens anteriores.

Essas evidências devem ficar em armazenamento privado, **fora do Git**.
Sem elas, a meta de 95% de liberação operacional não pode ser declarada e
não se devem distribuir convites reais. Esta rodada não altera dados no
banco, .env, infraestrutura, convidados nem dispositivos.
