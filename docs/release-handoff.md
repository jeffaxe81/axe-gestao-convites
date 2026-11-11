# Convites AXE — Entrega técnica da Release 1

Fechamento documental: **08/11/2026**. Aniversário da Isadora: **13/12/2026, 15h**, America/Sao_Paulo. Local ainda deve ser confirmado/configurado no painel.

## Código e pacote

A aplicação implementa RSVP de presenças/recusas, participantes, idade 0–12, link privado de edição, idempotência, painel de gestão, contagem interna do buffet e lembrancinhas, exportação CSV, e suporte a Docker Compose + MySQL. Inclui ferramentas de pré-check, backup/recuperação cifrada, geração de PDF e histórico operacional privado sem nomes/tokens.

A execução **verde** da CI do GitHub Actions inclui um artefato **isadora-release-1-source**: ZIP do código versionado, verificado para não conter `.env` nem arquivo de backup. O SHA-256 aparece no log. Retenção do artefato: **30 dias**.

**O ZIP não é um instalador e não contém credenciais ou banco de convidados.** A página `gh-pages` é somente uma prévia visual sem confirmação real, e não é a hospedagem de produção.

## Procedimento para publicação

1. Informar domínio definitivo e servidor (não constam nas configurações do projeto); instalar Docker/Compose e configurar proxy HTTPS ou Cloudflare Tunnel.
2. Criar arquivo `.env` **privado** no host com segredos únicos e hash de senha administrativa, `chmod 600 .env`. Não copiar credenciais ao GitHub ou chat.
3. Executar `python scripts/preflight.py --env-file .env`, depois `docker compose up -d --build --wait`. Deixar MySQL e porta 8080 não expostos ao público.
4. Executar de rede externa `python scripts/check_production.py --url https://DOMINIO_REAL`; registrar evidência de TLS, HSTS, política CSP, dados privados protegidos e cookie administrativo seguro.
5. Configurar backup cifrado **externo** e política de retenção; testar restauração no host definitivo com banco temporário, sem sobrescrever dados reais.
6. Gerar PDF **individual por família** com `python scripts/generate_invitation.py --family-link-stdin --check-production --output /PASTA-PRIVADA/convite-teste.pdf --venue "LOCAL_CONFIRMADO"`, colando o link secreto da família fictícia na entrada oculta. O modo `--url` é apenas modelo geral e **NÃO deve ser distribuído**. Consulte [procedimento de PDF individual](pdf-individual-por-familia.md).
7. Fazer homologação de PDF recebido via WhatsApp em **Android e iPhone físicos**; testar confirmação, recusa, edição, acompanhante, idade, perda de rede e reenvio.
8. Registrar revisão de segurança independente, aprovador e aceite de operação antes de distribuir os convites.

## Gate final

- [x] Regras, formulários, API, painel e proteção de acesso implementados
- [x] Testes automatizados, Docker, persistência e recuperação verificados em ambiente descartável na última CI verde
- [x] Empacotamento técnico preparado para gerar arquivo somente após CI verde
- [ ] Domínio, DNS, HTTPS e proxy/túnel no ambiente real
- [ ] Backup externo e restauração validados no host definitivo
- [ ] PDF via WhatsApp testado em Android e iPhone físicos
- [ ] Revisão de segurança e aceite operacional

**Situação: código da Release 1 mesclado à main com 230 testes aprovados; publicação ainda não liberada.** Barra de liberação: **86%** (6/7 etapas concluídas). Não tratar CI de código como teste de campo.

## Domínio opcional durante a finalização

O projeto pode ser concluído antes da escolha do DNS. Veja [guia de domínio flexível](dominio-flexivel.md). Para informar o domínio no futuro, execute `scripts/set_public_url.py --domain NOME` no servidor, recrie somente `app` e faça a checagem HTTPS. Não exige recompilar a aplicação nem alterar o MySQL.

## Verificação final do gate de publicação

Consultar [fechamento para 100%](fechamento-100.md). Há um manifesto-modelo para registrar seis evidências operacionais sem PII (`docs/release-evidence-template.json`) e um script `scripts/release_readiness.py` que recusa declarar o checklist completo enquanto faltar qualquer uma. A aplicação também recusa URLs públicas inseguras diretamente na inicialização, sem confiar apenas no pré-check opcional. A comprovação real de Android/iPhone, HTTPS e restauração de produção continua externa.

## Rastreabilidade do código na imagem Docker

Uma verificação local adicional está disponível em `scripts/check_deployed_revision.py --json`. A ferramenta compara o SHA do checkout limpo ao rótulo OCI do app em execução, depois de um build explicitamente etiquetado com `SOURCE_REVISION`. Veja [procedimento de identidade](identidade-imagem-deploy.md). Esta conferência não verifica bytes da imagem e **não** autoriza distribuição de convites.
