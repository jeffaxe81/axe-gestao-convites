# Conferência de versão visual publicada — Isadora

Objetivo: verificar se os quatro arquivos estáticos públicos entregues por
`https://isadora2anos.org` correspondem **byte a byte** à cópia do código
em avaliação. O diagnóstico é somente de leitura: faz quatro GETs HTTPS de
CSS/JavaScript, sem login, tokens, convidados ou alterações no banco.

## Pré-requisitos

- A aplicação já deve estar publicada por HTTPS e acessível de fora do servidor.
- Depois do merge aprovado, atualizar o checkout **para o commit exato da release**
  em ambiente controlado, registrar `git rev-parse HEAD` e exigir
  `git status --short` vazio. Não rodar `git pull` cegamente no host em produção.
- Executar de uma máquina com acesso público, sem necessidade de acessar MySQL.
- Não publicar a saída de `.env`, links individuais ou qualquer lista de famílias.

## Comandos

```bash
cd ~/Projetos/jeffaxe81/axe-gestao-convites
git rev-parse HEAD
git status --short
python scripts/check_deployed_assets.py --url https://isadora2anos.org --json
python scripts/check_production.py --url https://isadora2anos.org
```

Exemplo de resultado esperado do primeiro verificador:

```json
{"status":"PASS","read_only":true,"checked_assets":4,"files":["site.css","guest.js","admin.css","admin.js"],"backend_version_verified":false}
```

Se a checagem falhar, **não distribuir convites reais**. Verificar se o checkout
comparado está correto, se o contêiner foi atualizado e se o cache do CDN está
servindo uma versão antiga. Não corrigir uma divergência forçando migração ou
apagando volumes. A mensagem de erro informa apenas o nome do arquivo divergente.

**Limites:** a igualdade de CSS/JS não comprova a versão do código Python,
migrations, autenticação, banco ou configuração do túnel. Este teste complementa,
mas não substitui, CI aprovada no mesmo SHA, `check_production.py`, backup
externo com restauração, testes físicos Android/iPhone, revisão de segurança e
aceite explícito do organizador.

A ferramenta foi incluída como evolução técnica pós-CI #328; conferir CI da
PR e da `main` final antes de usar qualquer resultado como evidência de release.
