# Relatório administrativo de acompanhamento de convites

Acesse **/organizar** e faça login. Na seção **Distribuição e acompanhamento dos convites**, agora há:
- filtro **Interesse voluntário** (todos, demonstrou interesse, sem interesse registrado);
- botão **Exportar acompanhamento (CSV)**.

O CSV contém uma linha por família: identificador, responsável, telefone, situação do RSVP, envio registrado manualmente (com data UTC) e interesse voluntário (com data UTC). A exportação usa CSV UTF-8 com BOM, separador ponto e vírgula e proteção contra fórmulas de planilha.

**Não contém tokens, links privados, hashes nem senhas.** Ainda assim, inclui dados pessoais e só pode ser acessada com sessão de organizador. O servidor retorna `Cache-Control: no-store, private`, `X-Content-Type-Options: nosniff` e `Content-Disposition: attachment`. O painel evita iniciar download após logout ou expiração de sessão no meio da requisição.

A API é `GET /api/admin/invitation-followup.csv` e requer login. O filtro na página é local (não altera contadores gerais); o CSV inclui todas as famílias cadastradas, independentemente do filtro visual.

**Importante:** interesse é opt-in explícito e não comprova leitura integral. Envio registrado é uma anotação manual e não confirma entrega pelo WhatsApp. Nenhum dos dois confirma presença. Não há rastreamento oculto.

## Testes

`tests/integration/test_invitation_followup_export.py` verifica bloqueio sem autenticação, exportação vazia, família com interesse + recusa + envio manual, família pendente, escaping de fórmula, ausência de links/tokens e bloqueio após logout. CI e homologação em dispositivos físicos continuam critérios separados.
