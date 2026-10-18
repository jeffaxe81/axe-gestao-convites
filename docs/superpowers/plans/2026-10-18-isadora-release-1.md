# Isadora Release 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar o aplicativo web de confirmação de presença da Isadora, com painel privado, regras de buffet e lembrancinhas, edição com prazo, MySQL, Docker e evidências de testes.

**Architecture:** Monólito web com Flask: páginas públicas, páginas dos organizadores e API na mesma aplicação. MySQL mantém configurações, respostas e participantes em transações; o Compose executa aplicação e banco com volume persistente. A página pública recebe apenas dados próprios e informações da festa; contagens financeiras são calculadas no servidor e entregues exclusivamente ao painel autenticado.

**Tech Stack:** Python 3.12, Flask 3.1, SQLAlchemy 2.0, PyMySQL 1.1, Gunicorn, HTML/Jinja, CSS e JavaScript sem framework de frontend; MySQL 8.4; Docker Compose; pytest, Hypothesis e Playwright. Fixar versões completas das dependências resolvidas em arquivos de instalação antes de entregar a imagem.

**Spec:** `docs/superpowers/specs/2026-10-18-isadora-release-1-design.md`, publicada no commit `e6a0cea7086c7155b3d95d7e61880f53a1da3262`. O usuário autorizou seguir para desenvolvimento após a apresentação da especificação. Este documento é o plano técnico para revisão; não descreve código ou testes já executados.

## Global Constraints

- Evento: aniversário de dois anos da Isadora.
- Data e horário: domingo, 13/12/2026, às 15h, no fuso America/Sao_Paulo.
- Visual delicado e infantil, com amarelo-manteiga, margaridas e composição harmônica.
- Banco de dados MySQL, conforme escolha expressa do usuário.
- Docker Compose com dois serviços: aplicação e MySQL.
- O limite de quarenta considera apenas pessoas incluídas na contagem do buffet.
- Crianças até cinco anos são contabilizadas separadamente e não consomem esse limite.
- A lista de lembrancinhas inclui os nomes e o total de todas as crianças de zero a doze anos, inclusive.
- Recusas não entram em nenhuma contagem de presença, buffet ou lembrancinhas.
- A página pública e suas respostas de API não devem expor regras de cobrança, limite interno, contagens globais ou listas de outras famílias.
- Enquanto o prazo não estiver configurado, a edição permanece aberta; no instante limite e depois dele, a edição pelo convidado será encerrada.
- O prazo limita edição. Novas confirmações permanecem permitidas; quarenta é contador e alerta interno, sem bloqueio automático.
- Convite em PDF, envio de mensagens, domínio e hospedagem não integram esta entrega.
- Nenhuma funcionalidade da release 2 será incluída.

## Review Focus

1. Repetir um envio cuja resposta se perdeu na rede deve recuperar a mesma confirmação; usar a mesma chave com conteúdo diferente deve produzir conflito.
2. Duas abas editando a mesma família devem detectar conflito de revisão, sem uma apagar silenciosamente o trabalho da outra.
3. Nomes com acentos, apóstrofos, homônimos e caracteres de HTML devem ser preservados e exibidos como texto.
4. Uma mudança do prazo pelo organizador concorrente com uma edição precisa de decisão transacional consistente.
5. Reiniciar aplicação e banco deve preservar respostas, credenciais de edição e configuração; a ausência do banco deve impedir mensagem falsa de sucesso.

Esses cinco casos possuem testes atribuídos nas tarefas abaixo.

## Arquivos e responsabilidades

- `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`: configuração Python e dependências fixadas.
- `app/__init__.py`, `app/config.py`, `wsgi.py`: criação da aplicação, configuração e entrada do servidor.
- `app/domain.py`: validação, faixas etárias, contagens e prazo.
- `app/db.py`, `app/models.py`, `migrations/001_initial.sql`: conexão, esquema e migração versionada.
- `app/rsvp.py`: transações, idempotência, edição e controle de revisão.
- `app/security.py`: segredos de edição, sessão de organizador, CSRF e limites de requisição.
- `app/public.py`, `app/organizer.py`: contratos HTTP públicos e privados.
- `app/templates/index.html`, `app/templates/edit.html`, `app/static/guest.js`, `app/static/site.css`: experiência do convidado.
- `app/templates/admin.html`, `app/static/admin.js`: painel dos organizadores.
- `tests/unit/`, `tests/integration/`, `tests/e2e/`: validação das regras, MySQL real e navegador.
- `Dockerfile`, `compose.yaml`, `compose.test.yaml`, `.dockerignore`, `.env.example`: execução e teste isolados.
- `scripts/check_persistence.py`, `.github/workflows/ci.yml`, `README.md`, `docs/validation.md`: operação, CI, instalação e evidências.

## Contratos compartilhados

- `ParticipantInput(name: str, kind: Literal["CHILD", "OVER_12"], age_years: int | None)`. CHILD exige idade inteira de zero a doze; OVER_12 exige idade nula e representa pessoa acima de doze sem exigir sua idade exata.
- `RsvpInput(contact_name: str, attending: bool, participants: list[ParticipantInput])`. Na confirmação positiva, a primeira pessoa é o convidado principal e seu nome corresponde a contact_name; na recusa, a lista é vazia.
- `Counts(total: int, buffet: int, children_0_5: int, children_0_12: int, over_12: int)`.
- `EventSettings(venue: str | None, edit_deadline_utc: datetime | None, buffet_limit: int = 40)`. O início da festa é 2026-12-13T15:00:00-03:00.
- `RsvpReceipt(id: str, revision: int, edit_token: str, attending: bool)`. Respostas públicas não incluem Counts.
- Erros HTTP: 400 JSON malformado; 401 autenticação ausente/inválida; 403 edição encerrada ou CSRF inválido; 409 revisão/chave em conflito; 422 entrada inválida; 429 limite de requisições; 503 banco indisponível.

## Task 1: Regras e prazo testáveis

**Files:** criar `app/domain.py`, `app/config.py`, `pyproject.toml`, arquivos de dependências e `tests/unit/test_domain.py`.

**Interfaces:**
- Consumes: contratos compartilhados deste plano.
- Produces: `validate_rsvp(payload: dict) -> RsvpInput`; `count_participants(participants: Sequence[ParticipantInput]) -> Counts`; `can_edit(now_utc: datetime, deadline_utc: datetime | None) -> bool`.

- [ ] **Step 1: Escrever testes de regras antes da implementação.**

```python
def test_age_boundaries_and_souvenirs():
    people = children_with_ages(0, 5, 6, 12) + [over_12("Pessoa de 13 anos")]
    assert count_participants(people) == Counts(5, 3, 2, 4, 1)

def test_exact_deadline_is_closed():
    assert can_edit(limit - timedelta(microseconds=1), limit)
    assert not can_edit(limit, limit)
    assert not can_edit(limit + timedelta(microseconds=1), limit)
    assert can_edit(now, None)
```

Adicionar assertions de recusa com lista vazia; criança com idade 13, negativa, booleana ou fracionária rejeitada; nome vazio rejeitado; equivalência de instantes UTC e America/Sao_Paulo. Hypothesis gera listas válidas e compara Counts com um recálculo independente.

- [ ] **Step 2: Executar `python -m pytest tests/unit/test_domain.py -q`; confirmar falha pela ausência das funções.**
- [ ] **Step 3: Implementar as interfaces de domínio, normalização de espaços, limite de 160 caracteres por nome, máximo de 100 participantes por resposta e regras exatas da especificação.** Homônimos não são removidos.
- [ ] **Step 4: Reexecutar o comando e obter zero falhas; resolver dependências em ambiente isolado e fixar as versões nos arquivos de instalação.**
- [ ] **Step 5: Commit `feat: add RSVP counting and deadline rules`.**

## Task 2: MySQL persistente e transações

**Files:** criar `app/db.py`, `app/models.py`, `app/rsvp.py`, migração, `Dockerfile`, arquivos Compose, `.env.example`, `.dockerignore`, `tests/conftest.py` e `tests/integration/test_rsvp_store.py`.

**Interfaces:**
- Consumes: RsvpInput, Counts, EventSettings e validação da tarefa 1.
- Produces: `create_rsvp(session_factory, data: RsvpInput, submission_key: str, now_utc: datetime) -> RsvpReceipt`; `update_rsvp(session_factory, rsvp_id: str, token: str, expected_revision: int, data: RsvpInput, now_utc: datetime) -> RsvpReceipt`; `get_own_rsvp(session_factory, rsvp_id: str, token: str) -> dict`; `get_summary(session_factory) -> dict`.

- [ ] **Step 1: Escrever testes com MySQL real.**

```python
def test_retry_recovers_one_response(store):
    first = store.create(payload, submission_key="random-key")
    second = store.create(payload, submission_key="random-key")
    assert first.id == second.id
    assert first.edit_token == second.edit_token
    assert store.response_count() == 1

def test_stale_revision_cannot_overwrite(store):
    created = store.create(payload)
    store.update(created.id, created.edit_token, 1, changed_payload)
    with pytest.raises(RevisionConflict):
        store.update(created.id, created.edit_token, 1, other_payload)
```

Cobrir mesma chave com conteúdo diferente; rollback após falha no segundo acompanhante; edição positiva para negativa; nomes acentuados, apóstrofos e homônimos; verificação de que principal não é incluído duas vezes pelo fluxo.

- [ ] **Step 2: Executar `docker compose -f compose.test.yaml run --rm tests python -m pytest tests/integration/test_rsvp_store.py -q`; registrar a falha inicial no banco isolado.**
- [ ] **Step 3: Implementar esquema InnoDB/utf8mb4 e transações.** Configuração do evento em uma linha; respostas com UUID, status, revisão, digest de chave, digest de conteúdo e digest de segredo; participantes com posição única por resposta. Não persistir o segredo de edição em texto. Derivar um segredo recuperável por HMAC de chave de submissão aleatória e chave privada da aplicação, armazenando somente seu hash para autorização. Inserção concorrente usa unicidade da chave; edição usa revisão e transação, com bloqueio da configuração para decidir o prazo consistentemente.
- [ ] **Step 4: Reexecutar os testes com zero falhas.** Compose de teste usa projeto/volume próprios; o comando de limpeza nunca inclui o volume real. A aplicação usa usuário MySQL restrito ao seu banco, sem publicar a porta do banco. Criar CLI `python -m app.db migrate` idempotente, com tabela de migrações.
- [ ] **Step 5: Commit `feat: persist RSVP families in MySQL with transactional editing`.**

## Task 3: API pública e edição privada

**Files:** criar `app/__init__.py`, `app/public.py`, `app/security.py`, `wsgi.py`, `tests/integration/test_public_api.py` e `tests/integration/test_privacy.py`.

**Interfaces:**
- Consumes: interfaces das tarefas 1 e 2.
- Produces: `create_app(config: dict | None = None) -> Flask`; rotas `GET /api/event`, `POST /api/rsvps`, `GET /api/rsvps/<id>`, `PUT /api/rsvps/<id>`, `GET /health/live`, `GET /health/ready`.
- POST exige `Idempotency-Key` aleatória; GET/PUT de resposta exigem `Authorization: Bearer <edit_token>`; PUT exige revision.

- [ ] **Step 1: Escrever testes do contrato público.**

```python
def test_guest_cannot_read_another_response(client, family_a, family_b):
    response = client.get(f"/api/rsvps/{family_b.id}",
                          headers=bearer(family_a.edit_token))
    assert response.status_code == 401

def test_public_event_has_only_allowed_fields(client):
    assert set(client.get("/api/event").json) == {
        "name", "age", "starts_at", "timezone", "venue"
    }
```

Cobrir prazo encerrado, JSON malformado, corpo acima de 64 KiB, banco fora do ar com 503, submissão sem chave e reenvio após resposta simulada perdida. Testar listas de campos permitidos em todas as respostas públicas, incluindo erros.

- [ ] **Step 2: Executar `docker compose -f compose.test.yaml run --rm tests python -m pytest tests/integration/test_public_api.py tests/integration/test_privacy.py -q`; observar falhas iniciais de rotas.**
- [ ] **Step 3: Implementar rotas, schemas de saída explícitos e segredos.** Não compartilhar serializador de painel com convidado. Link privado de edição usa fragmento `/editar#<id>.<token>`; o segredo não é enviado na URL de requisições do servidor. Redigir logs sem corpos, tokens ou nomes. Limitar requisições por IP, sem confiar em cabeçalhos de proxy não configurado. Retornar sucesso somente após commit no banco.
- [ ] **Step 4: Reexecutar testes com zero falhas; GET readiness retorna 503 quando MySQL está indisponível.**
- [ ] **Step 5: Commit `feat: expose private-by-default guest RSVP API`.**

## Task 4: Autenticação e painel de dados dos organizadores

**Files:** criar `app/organizer.py`, completar `app/security.py`, `tests/integration/test_organizer.py` e `tests/integration/test_deadline_race.py`.

**Interfaces:**
- Consumes: create_app, get_summary, sessão MySQL e EventSettings.
- Produces: `GET /api/auth/csrf`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/admin/dashboard`, `PUT /api/admin/settings`.
- dashboard inclui respostas positivas/negativas, participantes, Counts e lista de crianças confirmadas; settings permite somente venue e edit_deadline.

- [ ] **Step 1: Escrever testes de autorização, contagens e configuração.**

```python
def test_private_dashboard_requires_login(client):
    assert client.get("/api/admin/dashboard").status_code == 401

def test_dashboard_counts_confirmed_only(admin, seeded_families):
    data = admin.get("/api/admin/dashboard").json
    assert data["counts"]["buffet"] == 3
    assert data["counts"]["children_0_12"] == 4
    assert len(data["souvenir_children"]) == 4
```

Cobrir login inválido, CSRF ausente, logout, limitação de tentativas, sessão sem privilégios após logout e configurações não permitidas. Criar teste com duas conexões MySQL: atualização de prazo concorrente com edição resolve pela ordem de bloqueio, sem aceitar edição com regra já encerrada.

- [ ] **Step 2: Executar `docker compose -f compose.test.yaml run --rm tests python -m pytest tests/integration/test_organizer.py tests/integration/test_deadline_race.py -q`; confirmar falhas iniciais.**
- [ ] **Step 3: Implementar login com hash de senha, segredo de sessão vindo do ambiente, renovação de sessão no login, cookies HttpOnly/SameSite e Secure quando em HTTPS.** Usar token CSRF de sessão nas operações administrativas. Configuração inicial não contém senha compartilhada fixa. Contagens consultam somente respostas positivas. Alertar internamente ao atingir ou ultrapassar quarenta, sem bloquear convidado.
- [ ] **Step 4: Reexecutar testes com zero falhas; comprovar que contagens e configurações não aparecem em respostas de convidado.**
- [ ] **Step 5: Commit `feat: add organizer authentication and private attendance dashboard`.**

## Task 5: Página de margaridas e formulário no celular

**Files:** criar templates index/edit, `app/static/site.css`, `app/static/guest.js` e `tests/e2e/test_guest.py`.

**Interfaces:**
- Consumes: contratos da API pública, Idempotency-Key e revision.
- Produces: páginas `/` e `/editar`; formulário com confirmação/recusa, convidado principal, acompanhantes e idade infantil; revisão, agradecimento e link privado.

- [ ] **Step 1: Escrever testes de navegador.**

```python
def test_mobile_confirmation_and_edit(page, live_app):
    page.set_viewport_size({"width": 390, "height": 844})
    complete_family(page, child_ages=[5, 6, 12])
    submit_twice(page)
    expect(page.get_by_role("status")).to_contain_text("presença")
    assert live_app.response_count() == 1

def test_names_render_as_text(page, live_app):
    complete_family(page, principal="<img src=x onerror=alert(1)>")
    assert page.locator("img[src=x]").count() == 0
```

Cobrir recusa, acompanhantes sem idade, edição pelo mesmo link, conflito de revisão apresentado sem perder os campos digitados, prazo fechado, indisponibilidade com preservação do formulário e teclado/foco. Validar ausência de dados do buffet no HTML/JavaScript entregue ao convidado.

- [ ] **Step 2: Executar `python -m pytest tests/e2e/test_guest.py -q` contra banco de testes; confirmar falha inicial das páginas.**
- [ ] **Step 3: Implementar página responsiva em amarelo-manteiga, branco e texto escuro, com margaridas em CSS/SVG e formulário legível.** Campos infantis aparecem somente quando aplicáveis. Preservar chave de submissão entre tentativas e só trocá-la ao iniciar outra resposta. A primeira pessoa é o principal. Usar textContent para nomes dinâmicos. A confirmação só aparece após sucesso persistido. Exibir opção para copiar/guardar o link privado, sem consulta pública por nome.
- [ ] **Step 4: Reexecutar testes Chromium em 390x844 e 1280x800 com zero falhas; verificar navegação por teclado e ausência de rolagem horizontal no formulário.**
- [ ] **Step 5: Commit `feat: add daisy-themed mobile RSVP and edit pages`.**

## Task 6: Interface do painel privado

**Files:** criar `app/templates/admin.html`, `app/static/admin.js` e `tests/e2e/test_organizer.py`.

**Interfaces:**
- Consumes: API de autenticação, dashboard e settings da tarefa 4.
- Produces: página `/organizar`, com login, listas, contadores, nomes das crianças e configuração de local/prazo.

- [ ] **Step 1: Escrever testes de interface.**

```python
def test_private_lists_and_settings(page, seeded_app):
    login_organizer(page)
    expect(page.get_by_test_id("buffet-count")).to_have_text("3")
    expect(page.get_by_test_id("souvenir-count")).to_have_text("4")
    update_venue(page, "Local definido")
    expect(page.get_by_test_id("venue")).to_have_value("Local definido")
```

Cobrir listas de recusas, famílias agrupadas, zero confirmações, edição do prazo com fuso explícito, perda de sessão e erro de gravação sem mensagem de sucesso. Comparar contador geral com a soma de crianças e pessoas acima de doze.

- [ ] **Step 2: Executar `python -m pytest tests/e2e/test_organizer.py -q`; observar falha inicial da interface.**
- [ ] **Step 3: Implementar o painel com números rotulados e listas nominais, sem exportação ou funcionalidades extras.** Dados privados só são solicitados após autenticação. Alteração de local mantém a URL pública; prazo vazio significa edição aberta.
- [ ] **Step 4: Reexecutar testes do painel e os testes públicos, obtendo zero falhas.**
- [ ] **Step 5: Commit `feat: add organizer lists and event settings interface`.**

## Task 7: Concorrência, Docker e evidências da entrega

**Files:** criar `tests/integration/test_concurrency.py`, `scripts/check_persistence.py`, `.github/workflows/ci.yml`, `README.md`, `docs/validation.md`; finalizar arquivos Docker.

**Interfaces:**
- Consumes: todos os contratos e comandos anteriores.
- Produces: suíte reproduzível e instruções `docker compose up -d --build --wait`, `docker compose -f compose.test.yaml run --rm tests` e relatório de validação.

- [ ] **Step 1: Escrever os testes de estresse e operação.**

```python
def test_parallel_duplicate_submission_creates_one_family(mysql_app):
    receipts = parallel_submit(same_key=True, workers=20)
    assert len({r.id for r in receipts}) == 1
    assert mysql_app.response_count() == 1

def test_parallel_families_keep_exact_counts(mysql_app):
    parallel_submit_distinct_families(workers=20, child_ages=[5, 6, 12])
    assert mysql_app.summary() == Counts(80, 60, 20, 60, 20)
```

Cada família do segundo teste tem uma pessoa acima de doze e três crianças; ultrapassar quarenta não bloqueia o envio. O teste de persistência cria uma resposta e prazo, recria os serviços sem remover volumes e confere os mesmos dados e a validade do link de edição. Testar banco parado, indisponibilidade HTTP e retomada sem duplicar a tentativa.

- [ ] **Step 2: Executar a suíte completa e registrar falhas reais; não tratar testes ignorados por falta de Docker/MySQL/navegador como validação desses componentes.**
- [ ] **Step 3: Corrigir somente problemas do escopo e configurar CI.** O CI sobe MySQL real, roda unidade/integração, instala o navegador para e2e e executa build/saúde/persistência do Compose. Aplicação roda sem root, sem servidor de desenvolvimento e com healthcheck; banco usa volume nomeado e segredos de teste isolados. Bloquear CI em caso de falha. Se GitHub Actions não puder executar, registrar a limitação e fornecer comandos para o ambiente Docker do usuário.
- [ ] **Step 4: Executar `python -m pytest tests/unit -q`, suítes MySQL/e2e e `python scripts/check_persistence.py`; conferir saídas, logs de CI e estado dos contêineres.** Registrar comandos, totais, falhas, commit e verificações não executadas. Checklist manual: Android e iPhone abrindo o link em PDF pelo WhatsApp, toque, teclado, nomes, prazo e agradecimento. Não marcar um dispositivo como validado sem teste nele.
- [ ] **Step 5: Commit `test: verify release 1 concurrency Docker persistence and privacy`; concluir somente após revisão final do conjunto e evidências.**

## Dependências e execução recomendada

Ordem: 1 → 2 → 3 → 4 → 5 → 6 → 7. As partes compartilham fortemente contratos de contagem, transação e autorização. Recomenda-se execução direta nesta sessão, com revisão final independente, para reduzir coordenação e manter o escopo pequeno. Execução com agentes por tarefa é uma alternativa se o usuário preferir.

Antes de implementar, revisar este plano e confirmar a forma de execução, conforme a habilidade writing-plans. O prazo de edição e o local continuam configuráveis; não exigem nova definição para iniciar.

## Limites de validação já observados

O ambiente consultado possui Python 3.12, Node e Git, mas o executável Docker não foi encontrado. Este fato não valida nem invalida o Compose: seus testes devem executar no CI ou em ambiente com Docker. Nenhum código de produto, contêiner ou teste desta release foi executado durante a preparação do plano.

## Referências técnicas primárias

- Flask: https://flask.palletsprojects.com/en/stable/installation/
- Integração SQLAlchemy/Flask: https://flask.palletsprojects.com/en/stable/patterns/sqlalchemy/
- MySQL 8.4 com Docker: https://dev.mysql.com/doc/refman/8.4/en/linux-installation-docker.html
- Linha LTS do MySQL: https://dev.mysql.com/doc/refman/8.4/en/mysql-releases.html
