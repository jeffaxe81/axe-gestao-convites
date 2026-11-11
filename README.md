# Gerenciador de Convites da Isadora 🌼

Aniversário de dois anos da Isadora — 13/12/2026, às 15h (America/Sao_Paulo). Local ainda a confirmar.

**Estado: aplicação integrada à `main`, com CI automatizada aprovada. A divulgação de convites reais depende de homologação operacional.**

**Situação verificada em 10/11/2026:** a `main` inclui cadastro Excel/CSV por família, links privados, preparação de WhatsApp sem envio automático, registro manual de distribuição, interesse voluntário e relatório CSV de acompanhamento. [CI #328 aprovada](https://github.com/jeffaxe81/axe-gestao-convites/actions/runs/42787828624) no commit `4ddc271`. O resultado de 230 testes citado abaixo é histórico, não a última contagem. **Prontidão técnica: 100%; liberação operacional: 86%.**

Antes de liberar o domínio, conferir também os arquivos públicos com o [verificador de versão publicada](docs/verificacao-versao-publicada.md). Essa comparação **não valida o backend** nem substitui os testes físicos e o aceite.

Para uma homologação coordenada no servidor e de uma rede externa, usar o [diagnóstico consolidado somente leitura](docs/diagnostico-consolidado.md). O comando informa gates automáticos aprovados e pendentes, mas nunca autoriza envio de convites reais.

## Barra de avanço verificado

`[██████████████░░] 86% — 6 de 7 etapas completas`

Ver [docs/progresso.md](docs/progresso.md). Os testes automatizados de navegador passaram. A liberação para uso real ainda depende da revisão de segurança e do checklist em Android e iPhone reais.

## Implementado

**Fluxo de confirmação em produção:** para evitar presenças anônimas não vinculadas a convidados, novas respostas precisam do **link individual** fornecido ao responsável pela família cadastrada. A página inicial orienta a obter o link com o organizador, sem formulário aberto; `POST /api/rsvps` retorna `403 INVITATION_REQUIRED`. A confirmação por `/convite#id.token` continua funcional, assim como a edição de respostas anteriores com seus tokens privados. O modo de testes preserva o endpoint legado exclusivamente para regressão, sem opção de desativar a exigência em produção. Essa nova regra precisa de homologação com famílias fictícias no servidor antes de liberar convites reais.

- Regras de confirmação positiva/negativa com convidados e acompanhantes.
- Crianças de 0 a 5 anos: lembrancinha, sem consumir buffet. Crianças de 6 a 12: buffet e lembrancinha. Acima de 12: buffet.
- Limite de 40 apenas como alerta interno; não bloqueia convidados.
- Persistência SQLAlchemy/MySQL com UUID, idempotência, revisão otimista e transações.
- API pública com token de edição, prazo e respostas limitadas à própria família.
- Autenticação dos organizadores com hash de senha, sessão e CSRF.
- API administrativa: confirmações/recusas, totais privados, lista de crianças, local e prazo.
- Exportação CSV privada: confirmação, recusa, faixa etária, buffet e lembrancinhas; proteção contra injeção de fórmulas.
- Página pública com tema margaridas/amarelo-manteiga e formulário para celular, revisão, agradecimento e link privado para editar.

O painel visual dos organizadores está implementado, com login, listas, indicadores, pesquisa de convidados (inclusive acompanhantes e sem distinção de acentos), atualização manual ou automática a cada 15/30/60 segundos e ajustes do local/prazo. A atualização preserva pesquisas e campos não salvos; sessões expiradas durante atualização, exportação ou gravação ocultam e limpam dados privados, e falha de logout nunca deixa listas visíveis.

## Homologação local segura (sem domínio)

Após criar `.env` privado, configurar senhas e iniciar `docker compose up -d --build --wait`:

```bash
python scripts/preflight.py --env-file .env --local
python scripts/check_local.py
python scripts/check_local.py --json
```

O verificador confirma oito endpoints locais: saúde do banco, dados públicos, página do convite, calendário, bloqueio das três APIs privadas e CSRF. **Não cria, altera ou remove confirmações; nunca transmite nomes, tokens ou senhas no relatório.** Aceita somente `127.0.0.1` ou `localhost`, bloqueia redirecionamentos e funciona sem domínio. Para testar gravação/edição, use convidados fictícios em ambiente descartável e o [checklist manual](docs/manual-checklist.md).

## Testes

**230 testes aprovados** na CI integral de 08/11/2026, com MySQL real, API, concorrência, Chromium e proteção HTTP. Docker Compose validado com reinício, persistência, backup e restauração isolada e criptografada. Incluem-se testes de respostas administrativas HTTP 200 inconsistentes, edições concorrentes, prazo após locks MySQL, geração de convite PDF com QR Code e validação de URL HTTPS segura.
**CI atual aprovada:** https://github.com/jeffaxe81/axe-gestao-convites/actions/runs/42478818971 (230 testes, Docker, MySQL e restauração). A [verificação técnica anterior de 25/10/2026](docs/release-1-final-verification.md) documenta os ensaios de concorrência/locks e continua válida como histórico. Ver execuções em:
https://github.com/jeffaxe81/axe-gestao-convites/actions

Para executar:

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m playwright install --with-deps chromium
python -m pytest -q
```

## Convite PDF com link para WhatsApp (geração offline)

O gerador não faz envio nem contém nomes de convidados. Instale as dependências operacionais fora do contêiner web:

```bash
python -m pip install -r requirements-ops.txt
python scripts/generate_invitation.py --preview --output /tmp/isadora-demonstracao.pdf
# Após homologar seu domínio HTTPS:
python scripts/generate_invitation.py --url https://convites.seu-dominio.com.br --check-production --output /tmp/isadora-convite.pdf --venue "Local confirmado"
```

O modo `--preview` produz uma demonstração marcada, **sem link** e não deve ser enviada. A geração final exige domínio HTTPS real; nunca usar endereço provisório, link de edição privada ou incluir tokens. Confirmar QR Code e botão em celulares antes de encaminhar o PDF via WhatsApp.

## Domínio opcional agora, configurável depois

O sistema pode operar localmente em `http://127.0.0.1:8080`, mesmo sem domínio escolhido. Após criar e proteger seu `.env` com segredos reais:

```bash
python scripts/set_public_url.py --local
python scripts/preflight.py --env-file .env --local
```

Quando o domínio for escolhido, não é necessário mudar código ou banco:

```bash
python scripts/set_public_url.py --domain convites.seudominio.com.br
python scripts/preflight.py --env-file .env
docker compose up -d --no-deps --force-recreate app
```

O novo domínio precisa de DNS/HTTPS real antes do envio, e o PDF definitivo deve ser gerado com a URL efetiva. Veja [configuração flexível](docs/dominio-flexivel.md).

## Execução local com Docker (validada no CI; produção pendente)

```bash
cp .env.example .env
# alterar senhas e segredos antes de iniciar
docker compose up -d --build --wait
```

Variáveis essenciais: MYSQL_USER, MYSQL_PASSWORD, MYSQL_ROOT_PASSWORD, TOKEN_SECRET, SESSION_SECRET, ORGANIZER_USERNAME, ORGANIZER_PASSWORD_HASH e APP_PUBLIC_URL.

O hash da senha do organizador pode ser gerado sem colocar a senha em comando ou arquivo usando:

```bash
python -c "from werkzeug.security import generate_password_hash; import getpass; print(generate_password_hash(getpass.getpass()))"
```

Copie o hash para o arquivo privado .env. Coloque o valor entre aspas simples porque ele contém sinais de dólar. Nunca versione credenciais reais.

A página pública recebe somente informações de RSVP, não as regras financeiras do buffet. A porta 8080 é vinculada a `127.0.0.1`; acesso externo requer proxy HTTPS no mesmo servidor. O ambiente de produção ainda não foi homologado.

Não habilite `TRUSTED_PROXY_HOPS=1` sem configurar um proxy local que SOBRESCREVA `X-Forwarded-For`. Veja o procedimento de segurança e os riscos remanescentes na documentação.

## Documentação

- [Especificação](docs/superpowers/specs/2026-10-18-isadora-release-1-design.md)
- [Plano](docs/superpowers/plans/2026-10-18-isadora-release-1.md)
- [Barra de progresso](docs/progresso.md)
- [Evidências verificadas](docs/validation.md)
- [Checklist manual pendente](docs/manual-checklist.md)
- [Seis frentes técnicas e critérios de fechamento](docs/frentes-paralelas.md)
- [Pacote técnico, implantação e critérios de aceite](docs/release-handoff.md)
- [Domínio opcional e configuração posterior](docs/dominio-flexivel.md)
- [Segurança para publicação e riscos](docs/security-deployment.md)
- [Backup, verificação de restauração e recuperação](docs/backup-restore.md)
- [Publicação HTTPS e smoke test sem alterar convites](docs/https-deployment.md)
- [Implantação opcional via Cloudflare Tunnel](docs/cloudflare-tunnel.md)
- [Antecipação de 1 mês, entregas e pendências](docs/antecipacao-1-mes.md)
- [Antecipação de 2 meses: histórico, buffet, impressão e homologação](docs/antecipacao-2-meses.md)
- [20 melhorias de usabilidade, calendário, acessibilidade e segurança](docs/entregas-20-melhorias.md)
- [Fechamento para 100% operacional e registro de evidências](docs/fechamento-100.md)

O PDF do convite agora pode ser gerado **offline** com botão e QR Code clicáveis por `scripts/generate_invitation.py`. O aplicativo não envia mensagens por WhatsApp: a distribuição é manual e fica bloqueada até homologação de domínio, HTTPS e dispositivos físicos.

## Operação da Release 1 (implantação pendente)

Foram incluídos scripts de backup do MySQL e verificação de restauração em banco temporário, além de um verificador de publicação HTTPS somente de leitura. O GitHub Actions foi ampliado para tentar backup + restauração após o teste de persistência; o teste real em CI confirmou o backup/restauração sem modificar a base original. A homologação em hospedagem real ainda é necessária.

Exemplos, riscos e procedimentos constam nos documentos operacionais acima. **Um dump SQL não é criptografado por estar comprimido.** Hospedagem real, restauração em ambiente definitivo, revisão independente de segurança e testes manuais de iPhone/Android permanecem obrigatórios antes da publicação.

## Entregas de operação antecipadas

- **Relatório CSV:** o organizador, após login em `/organizar`, pode clicar em *Exportar confirmações (CSV)*. O arquivo contém dados pessoais e deve permanecer restrito.
- **Criptografia AES-256-GCM:** instalar `python -m pip install -r requirements-ops.txt` e executar `python scripts/secure_backup.py --help`. Cifrar o backup antes de movê-lo para armazenamento externo; validar restauração.
- **Pré-checagem de produção:** executar `python scripts/preflight.py --env-file .env` (arquivo privado chmod 600). Este teste não substitui DNS/HTTPS efetivo.
- **Revisão mensal acelerada:** ver `docs/antecipacao-1-mes.md`.

A PR #1 foi mesclada à main em 08/11/2026. Isso não significa publicação. A prova de HTTPS e dispositivos físicos ainda é obrigatória.

## Entregas adicionais de novembro (em verificação)

- Histórico privativo de movimentações, somente tipo e data/hora, sem nomes de famílias ou tokens, com limite de 50 eventos recentes.
- Migração de banco aditiva 002 (tabela audit_events), sem apagar as confirmações existentes.
- CSV específico de buffet e lembrancinhas sem dados pessoais, além do relatório nominal já existente.
- Lista imprimível via navegador, em formato A4, que respeita o filtro de convidados escolhido.
- Verificação de backup com as quatro tabelas: evento, famílias, participantes e histórico.

A CI da versão integrada foi aprovada com 230 testes. Sem domínio HTTPS real e testes físicos, a liberação para convidados permanece bloqueada.

## Melhorias adicionais de 08/11 — verificação em CI

Foram adicionadas 20 melhorias no convite e painel: download do evento em calendário, data e contagem regressiva localizadas, aviso de internet indisponível sem confirmação falsa, contador/limite de acompanhantes, foco em erros, etapas e navegação por teclado, estado de edição e cópia de link, CSS acessível, diretivas de não-indexação, indicadores por família e faixa etária e CSV quantitativo detalhado. Consulte [a relação das 20 entregas](docs/entregas-20-melhorias.md). **A CI de 08/11/2026 aprovou este conjunto com 230 testes.**

## Segurança adicional na preparação final

A aplicação agora valida a origem HTTPS/loopback na própria inicialização e restringe cabeçalhos `Host` aceitos, mesmo quando o preflight não foi executado. Em HTTPS configura HSTS. A homologação humana dos seis controles restantes pode ser registrada com o modelo privado `docs/release-evidence-template.json` e verificada quanto à completude por `python scripts/release_readiness.py --evidence-file ARQUIVO_PRIVADO.json`. Essa verificação documental não comprova teste real nem autoriza publicar por si só.

## Reforço de confiabilidade móvel — navegador e rede instável

Em solicitações que fiquem pendentes por mais de 15 segundos, o formulário do convidado recupera o botão de envio, informa a incerteza e preserva os dados e a chave de idempotência para tentar novamente com segurança. Foram adicionados testes de RSVP/edição/retorno de conexão no Chromium (Android emulado) e WebKit (iPhone emulado). Veja [verificações de robustez móvel](docs/refino-final-mobile.md). Teste emulado não equivale a homologação física.

## Homologação em escala: 1 bilhão de operações simuladas

A suíte de CI contém um verificador nativo C11 que executa **1.000.000.000 de operações de estado sintéticas** (criação, reenvio, conflito, revisão antiga, edição, confirmação e recusa), com reconciliação periódica dos totais de buffet e lembrancinhas. Não são um bilhão de requisições HTTP ou dados de convidados reais. Uma camada separada realiza **443 tentativas reais de gravação** em rotas Flask com banco descartável e verifica os totais contra um oráculo independente. Relatório e método: [homologação de um bilhão de operações](docs/homologacao-bilhao.md). O status oficial deve corresponder à última CI verde da PR.
