# Gerenciador de Convites da Isadora 🌼

Aniversário de dois anos da Isadora — 13/12/2026, às 15h (America/Sao_Paulo). Local ainda a confirmar.

**Estado: desenvolvimento. Não divulgar ainda o endereço para convidados.**

## Barra de avanço verificado

`[██████████████░░] 86% — 6 de 7 etapas completas`

Ver [docs/progresso.md](docs/progresso.md). Os testes automatizados de navegador passaram. A liberação para uso real ainda depende da revisão de segurança e do checklist em Android e iPhone reais.

## Implementado

- Regras de confirmação positiva/negativa com convidados e acompanhantes.
- Crianças de 0 a 5 anos: lembrancinha, sem consumir buffet. Crianças de 6 a 12: buffet e lembrancinha. Acima de 12: buffet.
- Limite de 40 apenas como alerta interno; não bloqueia convidados.
- Persistência SQLAlchemy/MySQL com UUID, idempotência, revisão otimista e transações.
- API pública com token de edição, prazo e respostas limitadas à própria família.
- Autenticação dos organizadores com hash de senha, sessão e CSRF.
- API administrativa: confirmações/recusas, totais privados, lista de crianças, local e prazo.
- Exportação CSV privada: confirmação, recusa, faixa etária, buffet e lembrancinhas; proteção contra injeção de fórmulas.
- Página pública com tema margaridas/amarelo-manteiga e formulário para celular, revisão, agradecimento e link privado para editar.

O painel visual dos organizadores está implementado, com login, listas, indicadores, pesquisa de convidados (inclusive acompanhantes e sem distinção de acentos), atualização manual ou automática a cada 15/30/60 segundos e ajustes do local/prazo. A atualização preserva pesquisas e campos não salvos; sessões expiradas ocultam dados privados.

## Testes

**137 testes aprovados** em 25/10/2026, com MySQL real, API, concorrência, Chromium e proteção HTTP. Docker Compose validado com reinício, persistência, backup e restauração isolada e criptografada. Incluem-se testes para rejeitar respostas administrativas HTTP 200 incompletas ou com totais incoerentes, edições concorrentes e prazo verificado após bloqueios MySQL.
Evidência da execução atual: [fechamento técnico de 25/10/2026](docs/release-1-final-verification.md). A execução local incluiu MySQL real, Chromium e Compose; a CI do commit enviado deve ser conferida na PR. Ver execuções em:
https://github.com/jeffaxe81/axe-gestao-convites/actions

Para executar:

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m playwright install --with-deps chromium
python -m pytest -q
```

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
- [Segurança para publicação e riscos](docs/security-deployment.md)
- [Backup, verificação de restauração e recuperação](docs/backup-restore.md)
- [Publicação HTTPS e smoke test sem alterar convites](docs/https-deployment.md)
- [Antecipação de 1 mês, entregas e pendências](docs/antecipacao-1-mes.md)

A produção e o envio do convite em PDF pelo WhatsApp são atividades externas a este aplicativo. Domínio, hospedagem e validação manual Android/iPhone estão pendentes.

## Operação da Release 1 (implantação pendente)

Foram incluídos scripts de backup do MySQL e verificação de restauração em banco temporário, além de um verificador de publicação HTTPS somente de leitura. O GitHub Actions foi ampliado para tentar backup + restauração após o teste de persistência; o teste real em CI confirmou o backup/restauração sem modificar a base original. A homologação em hospedagem real ainda é necessária.

Exemplos, riscos e procedimentos constam nos documentos operacionais acima. **Um dump SQL não é criptografado por estar comprimido.** Hospedagem real, restauração em ambiente definitivo, revisão independente de segurança e testes manuais de iPhone/Android permanecem obrigatórios antes da publicação.

## Entregas de operação antecipadas

- **Relatório CSV:** o organizador, após login em `/organizar`, pode clicar em *Exportar confirmações (CSV)*. O arquivo contém dados pessoais e deve permanecer restrito.
- **Criptografia AES-256-GCM:** instalar `python -m pip install -r requirements-ops.txt` e executar `python scripts/secure_backup.py --help`. Cifrar o backup antes de movê-lo para armazenamento externo; validar restauração.
- **Pré-checagem de produção:** executar `python scripts/preflight.py --env-file .env` (arquivo privado chmod 600). Este teste não substitui DNS/HTTPS efetivo.
- **Revisão mensal acelerada:** ver `docs/antecipacao-1-mes.md`.

A PR permanece como rascunho, sem publicar a página para convidados. A prova de publicação em domínio real e os testes em dispositivos físicos ainda são obrigatórios.
