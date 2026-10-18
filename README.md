# Gerenciador de Convites da Isadora 🌼

Aniversário de dois anos da Isadora — 13/12/2026, às 15h (America/Sao_Paulo). Local ainda a confirmar.

**Estado: desenvolvimento. Não divulgar ainda o endereço para convidados.**

## Barra de avanço verificado

`[█████████░░░░░░░] 57% — 4 de 7 etapas completas`

Ver [docs/progresso.md](docs/progresso.md). Os testes com navegadores estão sendo implementados, e o aplicativo ainda exige validação antes do uso real.

## Implementado

- Regras de confirmação positiva/negativa com convidados e acompanhantes.
- Crianças de 0 a 5 anos: lembrancinha, sem consumir buffet. Crianças de 6 a 12: buffet e lembrancinha. Acima de 12: buffet.
- Limite de 40 apenas como alerta interno; não bloqueia convidados.
- Persistência SQLAlchemy/MySQL com UUID, idempotência, revisão otimista e transações.
- API pública com token de edição, prazo e respostas limitadas à própria família.
- Autenticação dos organizadores com hash de senha, sessão e CSRF.
- API administrativa: confirmações/recusas, totais privados, lista de crianças, local e prazo.
- Página pública com tema margaridas/amarelo-manteiga e formulário para celular, revisão, agradecimento e link privado para editar.

O painel visual dos organizadores **ainda não foi implementado**.

## Testes

No último CI validado antes dos testes de navegador: **61 testes aprovados**, incluindo MySQL real e testes HTTP.
A suíte headless Chromium está sendo adicionada. Ver execuções em:
https://github.com/jeffaxe81/axe-gestao-convites/actions

Para executar:

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m playwright install --with-deps chromium
python -m pytest -q
```

## Execução local com Docker (ainda em validação)

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

A página pública recebe somente informações de RSVP, não as regras financeiras do buffet. Em produção, usar domínio HTTPS e segredos fortes.

## Documentação

- [Especificação](docs/superpowers/specs/2026-10-18-isadora-release-1-design.md)
- [Plano](docs/superpowers/plans/2026-10-18-isadora-release-1.md)
- [Barra de progresso](docs/progresso.md)

A produção e o envio do convite em PDF pelo WhatsApp são atividades externas a este aplicativo. Domínio, hospedagem e validação manual Android/iPhone estão pendentes.
