# Convites AXE — Entrega técnica da Release 1

Fechamento documental: **08/11/2026**. Aniversário da Isadora: **13/12/2026, 15h**, America/Sao_Paulo. Local ainda deve ser confirmado/configurado no painel.

## Código e pacote

A aplicação implementa RSVP de presenças/recusas, participantes, idade 0–12, link privado de edição, idempotência, painel de gestão, contagem interna do buffet e lembrancinhas, exportação CSV, e suporte a Docker Compose + MySQL. Inclui ferramentas de pré-check, backup/recuperação cifrada, geração de PDF e histórico operacional privado sem nomes/tokens.

A execução **verde** da CI do GitHub Actions inclui um artefato **isadora-release-1-source**: ZIP do código versionado, verificado para não conter `.env` nem arquivo de backup. O SHA-256 aparece no log. Retenção do artefato: **30 dias**.

**O ZIP não é um instalador e não contém credenciais ou banco de convidados.** A página `gh-pages` é somente uma prévia visual sem confirmação real, e não é a hospedagem de produção.

## Procedimento para publicação futura (fora do escopo técnico atual)

1. Informar domínio definitivo e servidor (não constam nas configurações do projeto); instalar Docker/Compose e configurar proxy HTTPS ou Cloudflare Tunnel.
2. Criar arquivo `.env` **privado** no host com segredos únicos e hash de senha administrativa, `chmod 600 .env`. Não copiar credenciais ao GitHub ou chat.
3. Executar `python scripts/preflight.py --env-file .env`, depois `docker compose up -d --build --wait`. Deixar MySQL e porta 8080 não expostos ao público.
4. Executar de rede externa `python scripts/check_production.py --url https://DOMINIO_REAL`; registrar evidência de TLS, HSTS, política CSP, dados privados protegidos e cookie administrativo seguro.
5. Configurar backup cifrado **externo** e política de retenção; testar restauração no host definitivo com banco temporário, sem sobrescrever dados reais.
6. Gerar PDF **individual por família** com `python scripts/generate_invitation.py --family-link-stdin --check-production --output /PASTA-PRIVADA/convite-teste.pdf --venue "LOCAL_CONFIRMADO"`, colando o link secreto da família fictícia na entrada oculta. O modo `--url` é apenas modelo geral e **NÃO deve ser distribuído**. Consulte [procedimento de PDF individual](pdf-individual-por-familia.md).
7. Fazer homologação de PDF recebido via WhatsApp em **Android e iPhone físicos**; testar confirmação, recusa, edição, acompanhante, idade, perda de rede e reenvio.
8. Registrar revisão de segurança independente, aprovador e aceite de operação antes de distribuir os convites.

## Proteção contra confirmações sem convite

Em produção, a rota genérica de criação `POST /api/rsvps` foi desativada por padrão e não pode ser reativada via configuração de produção: retorna HTTP `403 INVITATION_REQUIRED`, sem escrever no banco. O formulário na página inicial `/` fica indisponível para novas respostas; o convidado deve abrir seu link individual `/convite#id.token`, associado ao registro de família importado. Tokens legítimos de edição das respostas anteriores continuam válidos. Confirmar o comportamento em homologação com famílias fictícias, inclusive dados inválidos e contagem antes/depois. Não alterar as tabelas nem apagar registros existentes durante a implantação.

O teste de persistência `scripts/check_persistence.py` é **exclusivo da CI descartável**: cria família fictícia por importação administrativa, confirma via token individual, testa rejeição de RSVP anônimo e recria os serviços Docker de teste para validar volume MySQL. Por alterar dados e contêineres, ele se recusa a iniciar fora do GitHub Actions e **não pode ser utilizado no servidor `policorp`**. No servidor real, usar somente os verificadores de leitura e procedimentos de homologação supervisionados.

## Escopo de aceite técnico (atualizado em 12/11/2026)

**Por solicitação do responsável, os testes em ambiente real foram excluídos
do escopo desta etapa de desenvolvimento.** Isso inclui ensaios presenciais
com Android/iPhone, WhatsApp efetivo, validação no `policorp`, restauração
externa de produção e prova de HTTPS de campo. Eles não devem ser exigidos
para considerar **a entrega técnica** finalizada.

A conclusão do escopo técnico depende exclusivamente de uma CI verde na
`main`, com testes unitários, E2E automatizados, Docker descartável,
persistência e restauração de testes. O relatório pode ser obtido por:

```bash
python scripts/release_readiness.py --scope technical \
  --sha ffbf57d1e8fd86d8871c61ef7f2929ff22164f07 \
  --run-id 43351834734 --json
```

Use sempre o SHA e o número da CI **mais recentes e correspondentes** à
`main`, caso outros commits sejam integrados. O resultado `technical_completion_percent=100`
significa apenas desenvolvimento e testes automatizados concluídos;
`operational_status=NOT_EVALUATED`, `ready_for_publication=false` e
`release_approved=false` impedem interpretar essa conclusão como
homologação de produção.

As verificações reais permanecem documentadas como procedimento separado e
**não realizado**, caso a publicação pública seja solicitada futuramente.
Não declarar execução fictícia de testes nem divulgar convites reais com base
apenas neste aceite técnico.

## Critérios de aceite da entrega técnica (sem testes reais)

- [x] Regras, formulários, API, painel e proteção de acesso implementados
- [x] Testes automatizados, Docker, persistência e recuperação verificados em ambiente descartável na CI verde da `main`
- [x] Empacotamento técnico preparado para gerar arquivo somente após CI verde

### Fora de escopo desta entrega, não executado nem homologado

- DNS, HTTPS e proxy/túnel no ambiente real
- Backup externo e restauração no host definitivo
- PDF/WhatsApp e RSVP em Android e iPhone físicos
- Revisão independente de segurança e aceite operacional para distribuição pública

Essas verificações **não impedem o encerramento do escopo técnico**. Entretanto,
sem elas não há comprovação de prontidão operacional ou autorização de produção.

**Situação desta entrega: escopo técnico concluído em 100%, condicionado à CI atual da main.** Testes reais excluídos desta etapa por solicitação. A antiga métrica de liberação operacional (86%, 6/7) é histórica e **não se aplica ao aceite técnico**; publicação pública continua não avaliada e não liberada.

## Domínio opcional durante a finalização

O projeto pode ser concluído antes da escolha do DNS. Veja [guia de domínio flexível](dominio-flexivel.md). Para informar o domínio no futuro, execute `scripts/set_public_url.py --domain NOME` no servidor, recrie somente `app` e faça a checagem HTTPS. Não exige recompilar a aplicação nem alterar o MySQL.

## Verificação futura do gate de publicação (fora do escopo técnico atual)

Consultar [fechamento para 100%](fechamento-100.md). Há um manifesto-modelo para registrar seis evidências operacionais sem PII (`docs/release-evidence-template.json`) e um script `scripts/release_readiness.py` que recusa declarar o checklist completo enquanto faltar qualquer uma. A aplicação também recusa URLs públicas inseguras diretamente na inicialização, sem confiar apenas no pré-check opcional. A comprovação real de Android/iPhone, HTTPS e restauração de produção continua externa.

## Rastreabilidade do código na imagem Docker

Uma verificação local adicional está disponível em `scripts/check_deployed_revision.py --json`. A ferramenta compara o SHA do checkout limpo ao rótulo OCI do app em execução, depois de um build explicitamente etiquetado com `SOURCE_REVISION`. Veja [procedimento de identidade](identidade-imagem-deploy.md). Esta conferência não verifica bytes da imagem e **não** autoriza distribuição de convites.
