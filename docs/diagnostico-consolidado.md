# Diagnóstico consolidado de homologação — gestor de convites

Este comando agrega os verificadores existentes, sempre **somente leitura**:
`preflight` da configuração local, saúde HTTP loopback, HTTPS externo,
controles de privacidade da página pública e hashes SHA-256 dos assets.

**Não publica o aplicativo, não testa o envio de WhatsApp e não modifica RSVP,
MySQL, volumes, senhas, DNS ou Cloudflare.** Nunca substitui homologação real.

## Como executar

Partindo de um checkout limpo e da revisão que será homologada:

```bash
cd ~/Projetos/jeffaxe81/axe-gestao-convites
git rev-parse HEAD
git status --short

# No host policorp, após garantir que a aplicação já foi iniciada com segurança:
python scripts/diagnose_release.py --url https://isadora2anos.org \
  --env-file .env --local-url http://127.0.0.1:8080 \
  --require-local-gates --json

# Em outra rede, para verificar acesso externo, sem disponibilizar o .env:
python scripts/diagnose_release.py --url https://isadora2anos.org --json
```

O teste externo executado **no mesmo host** não comprova alcance a partir de
uma operadora móvel. Exigir comprovação a partir de uma rede independente.

Se houver proxy configurado com `TRUSTED_PROXY_HOPS=1`, somente acrescente
`--allow-proxy-hop` depois de verificar que o proxy local reescreve
`X-Forwarded-For`, jamais por conveniência para silenciar avisos.

O utilitário sempre confere:
- URL HTTPS pública, sem caminho, query, porta ou credenciais;
- SHA Git do checkout e ausência de modificações;
- API pública, proteção de endpoints administrativos, CSP/HSTS e cookies HTTPS;
- quatro arquivos CSS/JS iguais byte a byte aos do checkout.

Se passar `--env-file`, valida os campos obrigatórios, permissões do arquivo
e igualdade de `APP_PUBLIC_URL` com a URL solicitada. Se passar
`--local-url`, valida também os oito checks locais de leitura. Checagens
não solicitadas aparecem explicitamente como `NOT_TESTED`.

**No host `policorp`, use `--require-local-gates`.** O modo estrito exige
ambos `--env-file` e `--local-url`; a ausência de qualquer um bloqueia
o resultado **antes de consultar a rede**. O campo `local_gate_coverage`
indica `NOT_TESTED`, `PARTIAL` ou `COMPLETE`; `host_checks_ready` só é
`true` quando os dois gates locais e todos os demais checks automáticos
passaram. Sem o modo estrito, uma execução externa pode retornar
`AUTOMATED_PASS` com cobertura local incompleta — isso **não** valida o host.
Nenhum desses campos autoriza convites reais.

## Como interpretar

- `BLOCKED`: algum requisito automático falhou; retorno do processo 1.
- `AUTOMATED_PASS`: todas as verificações **solicitadas** passaram; retorno 0.
- `release_approved` permanece **false em qualquer caso**.
- `human_gates_pending` lista sempre as seis comprovações finais que
  dependem do ambiente real e de aceite humano.

O relatório suprime mensagens de exceção e jamais apresenta conteúdo de
arquivos `.env`, cookies, links de convidados ou resposta bruta do servidor.

A igualdade dos arquivos públicos **não comprova o commit Python executado**,
a migração do MySQL, a configuração dos contêineres ou a versão da API.
Correlacionar manualmente SHA, imagem/contêiner e registro de implantação.

## Últimos gates de liberação

1. DNS/HTTPS e Cloudflare Tunnel confirmados **de uma rede externa**.
2. Backup cifrado externo e restauração isolada no servidor definitivo.
3. Abertura e confirmação com uma família fictícia em Android físico.
4. Mesmo roteiro em iPhone físico, incluindo redes instáveis.
5. Revisão de segurança independente e tratamento dos achados.
6. Autorização explícita do organizador.

Não usar celulares de convidados reais para ensaios antes do aceite.
Manter bloqueado o envio de convites reais até as seis evidências.
Consultar `docs/homologacao-policorp-cloudflare.md` e
`docs/verificacao-versao-publicada.md`.

## Validação de desenvolvimento

```bash
python -m pytest -q tests/test_diagnose_release.py
```

A suíte geral da PR e a CI da `main` após o merge devem estar verdes.
