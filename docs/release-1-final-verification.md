# Release 1 — verificação técnica de 25/10/2026

## Resultado

Código e validação automatizada concluídos nesta sessão, partindo do commit `977c9d58eb99acbe290814353b731079d86d689e` na branch `feat/isadora-release-1`. A homologação de produção permanece pendente; a PR #1 continua em rascunho e a barra geral permanece em 86% (6/7 etapas).

Não houve publicação, merge, envio de mensagens ou utilização de dados reais de convidados. O ambiente Compose usou credenciais aleatórias descartáveis e famílias sintéticas.

## Revisão independente e correção

Um segundo agente realizou revisão estática do conjunto: especificação, plano, regras, transações, APIs, autenticação, interfaces, Compose e ferramentas operacionais. Encontrou uma questão importante: o horário era capturado antes da aquisição dos locks de banco. Uma edição que aguardasse bloqueada até o prazo poderia ser aceita com horário antigo.

A regressão foi reproduzida com MySQL real: uma transação manteve o lock de `event_settings`, uma requisição PUT ficou aguardando e o relógio controlado avançou até o instante limite. Antes da correção, retornou HTTP 200 em vez de 403. A API agora fornece um relógio avaliado dentro da transação, depois dos locks de configuração e família. Um pedido recebido antes do prazo pode ser recusado se só conseguir adquirir os locks no instante limite ou depois. Esta decisão segue a regra estrita da especificação; o custo é rejeitar um pedido que chegou antes do limite mas ficou em espera.

Três casos novos verificam:

- Duas edições da revisão 1: exatamente uma vence, a outra recebe conflito; nomes/participantes permanecem coerentes e a revisão final é 2.
- O relógio atinge o prazo durante a espera: HTTP 403, sem alterar revisão ou participantes.
- O organizador encerra o prazo em transação concorrente: a edição aguardando observa a configuração efetivamente gravada e é recusada.

Nenhuma outra questão crítica ou importante foi identificada nessa revisão. Esta é uma revisão independente por agente, não uma auditoria externa nem aceite de operação em produção. A correção foi verificada por regressão antes/depois e suíte integral; não houve segunda rodada de revisão.

## Testes executados

Ambiente isolado Python 3.12, MySQL 8.4 em contêiner dedicado `isadora_test` e Chromium do Playwright 1.56. Variáveis de conexão abaixo representam somente o ambiente descartável; não usar banco de produção.

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt -r requirements-ops.txt
python -m playwright install chromium
# Configurar TEST_DATABASE_URL para o MySQL descartável com nome *_test.
python -m pytest tests/integration/test_concurrency_mysql.py -q
python -m pytest -q
```

Resultados observados:

| Execução | Resultado |
| --- | --- |
| Novos testes contra código anterior | 1 falhou, 4 passaram; falha: prazo durante espera retornou 200 |
| Concorrência após correção | 5 passaram em 1,45 s |
| Suíte integral com MySQL e Chromium | **137 passaram em 51,39 s, nenhum skip** |
| `git diff --check` | Sem erros |

O primeiro ensaio local sem `TEST_DATABASE_URL` registrou 131 aprovados e 6 skips; não foi usado como evidência de MySQL. A execução integral posterior incluiu todos esses casos.

## Docker, persistência e recuperação

Imagem construída e Compose iniciado com os dois serviços saudáveis. O build local montou o bundle de certificados do ambiente como secret BuildKit em receita temporária ignorada pelo Git; o Dockerfile de produção não foi alterado. A aplicação ficou em `127.0.0.1:8080`, sem URL pública.

Comandos operacionais executados:

```bash
docker compose up -d --no-build --wait
python scripts/check_persistence.py
python scripts/backup_mysql.py backup --output /caminho-fora-do-repo/isadora-release.sql.gz
python scripts/backup_mysql.py verify-restore --input /caminho-fora-do-repo/isadora-release.sql.gz
```

- `check_persistence.py`: aprovado; requisições repetidas mantiveram uma família; token, nomes e local sobreviveram à recriação de aplicação e banco com o mesmo volume.
- Backup com permissão 0600; restauração em banco temporário, comparando as três tabelas com a origem: aprovada.
- AES-256-GCM com frase aleatória em memória: cifragem/decifragem aprovadas, comparação binária idêntica.
- Restauração do arquivo decifrado em outro banco temporário: aprovada, três tabelas idênticas.
- Banco original não substituído; bancos temporários removidos pela ferramenta.

Os logs desta execução ficam no workspace da sessão em `/workspace/isadora-*.log`; não contêm evidência de produção. A CI do commit enviado é uma verificação adicional e deve ser consultada na [PR #1](https://github.com/jeffaxe81/axe-gestao-convites/pull/1).

## O que falta para encerrar a homologação

O ambiente não tem domínio, servidor definitivo ou credenciais de hospedagem configurados. Também não tem Android/iPhone físicos. Por isso, não é possível registrar aprovação desses pontos a partir dos testes automatizados.

1. Operador informa domínio/hospedagem e disponibiliza acesso seguro ao ambiente final, sem senhas no chat ou no repositório.
2. Implantar e verificar DNS, HTTPS e proxy conforme `docs/https-deployment.md`; executar preflight e `check_production.py` no domínio real.
3. Configurar armazenamento externo cifrado, retenção e recuperação; executar restauração no ambiente definitivo.
4. Responsável testa os fluxos reais no Android e iPhone via PDF/WhatsApp e registra dispositivo/data/evidência em `docs/manual-checklist.md`.
5. Registrar aceite técnico/operacional antes de liberar convidados e concluir a PR.

Não substituir esses ensaios por emulação de navegador nem marcar a release como 100% sem as evidências reais. Escopo de novas funcionalidades encerrado; as pendências são de homologação desta release.
