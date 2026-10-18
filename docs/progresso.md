# Evolução — gerenciador de convites da Isadora

Referência: 18/10/2026.

**Barra de progresso verificado:** `[█████████░░░░░░░] 57%` — 4 de 7 etapas aprovadas em testes automatizados.

| Etapa | Situação | Evidência |
| --- | --- | --- |
| 1. Regras e prazo | Concluída | Testes de idade, presença e limite temporal |
| 2. Banco MySQL e transações | Concluída inicialmente | Testes de persistência com MySQL real no CI; estresse na etapa 7 |
| 3. API RSVP/edição | Concluída inicialmente | HTTP, tokens, idempotência, privacidade, erros e revisão |
| 4. Autenticação e painel de dados | Concluída inicialmente | Sessão, CSRF, login, listas privadas, contadores e configuração |
| 5. Página do convidado | Interface implementada; E2E em validação | Formulário responsivo, recusa, acompanhante, revisão, link privado, suíte Chromium |
| 6. Interface dos organizadores | Pendente | Telas de login, listas e configurações |
| 7. Operação e ensaios finais | Pendente | Docker Compose real, concorrência, persistência, Android/iPhone, revisão de segurança |

**Testes aprovados:** 61 no GitHub Actions, incluindo MySQL 8.4 e verificação de presença das páginas. A suíte de navegador Chromium está sendo adicionada e só será contabilizada quando houver evidência de execução verde. Execuções: https://github.com/jeffaxe81/axe-gestao-convites/actions

**Critério:** etapas validadas / 7, arredondando a percentagem. 1=14%, 2=29%, 3=43%, 4=57%, 5=71%, 6=86%, 7=100%.

**Restrições:** CI HTTP usa SQLite em fixtures controladas e MySQL dedicado para a integração de persistência. O Compose completo e a execução em aparelhos físicos não foram validados. Não divulgar a aplicação para convidados nesta fase.

**Festa:** domingo, 13/12/2026, 15h, fuso America/Sao_Paulo. Local editável pelos organizadores. Não expor limite de buffet ou contagens em respostas públicas. Convite PDF e envio por WhatsApp não fazem parte desta release.
