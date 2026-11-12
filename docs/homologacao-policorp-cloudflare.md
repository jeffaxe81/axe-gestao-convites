# Homologação controlada — policorp e isadora2anos.org

> Procedimento preparado, **não executado no servidor policorp**. Não envolve publicação automática, nem autorização para enviar convites reais.

## Arquitetura validável

- Convidados: `https://isadora2anos.org/convite#<uuid>.<token>` (link individual no fragmento).
- Organização: `https://isadora2anos.org/organizar` (exige autenticação).
- Cloudflare Tunnel gerenciado: rota pública `isadora2anos.org` apontando para `http://localhost:8080`, **somente se cloudflared executar no host policorp**. Se cloudflared estiver em contêiner, usar um destino acessível a esse contêiner, nunca supor que localhost aponte para o host.
- Aplicação Docker: binding `127.0.0.1:8080`; MySQL restrito à rede interna do Compose. Não publicar a porta 3306.
- Cloudflare Tunnel fornece transporte e roteamento; **não autentica automaticamente** o painel nem substitui backup, WAF, revisão de segurança e controle de acesso.

## Conferência de configuração, sem expor senhas

No servidor, a partir do repositório e após backup:

```bash
cd ~/Projetos/jeffaxe81/axe-gestao-convites
git status --short
sudo docker compose ps
sudo systemctl is-active cloudflared
curl --fail --silent --show-error http://127.0.0.1:8080/health/ready
```

Verificar **localmente**, sem compartilhar o conteúdo do `.env`, se `APP_PUBLIC_URL=https://isadora2anos.org`, `TRUSTED_PROXY_HOPS=0` inicialmente e se credenciais/senhas estão preenchidas e distintas. Aplicar `chmod 600 .env` se necessário. Nunca executar `docker compose down -v`, `docker volume prune`, substituição automática de segredos ou importação com dados reais durante homologação.

Depois de confirmar que os arquivos são os da versão em avaliação:

```bash
python scripts/preflight.py --env-file .env
curl -I https://isadora2anos.org/
python scripts/check_production.py --url https://isadora2anos.org
```

O script de produção deve executar fora do servidor ou em rede externa para comprovar acessibilidade pública. Ele apenas lê endpoints; valida TLS, resposta de saúde, ausência de informações privadas, não-cache, CSP, anti-clickjacking, HSTS e atributos de cookie. Uma passagem nele **não prova** entrega dos convites nem substitui homologação real.

## Controle de riscos

1. Configurar o hostname público no painel Cloudflare com rota correta e DNS apropriado; não publicar serviços de banco ou administração Docker.
2. Verificar limites de requisição no WAF: com `TRUSTED_PROXY_HOPS=0` a aplicação pode ver a conexão de origem do túnel e compartilhar um limite local entre convidados; não alterar para 1 sem proxy que reescreva cabeçalhos de cliente com segurança.
3. Não aplicar desafio Cloudflare indiscriminadamente a `/api/*`, pois isso pode interromper o RSVP no navegador. Política de proteção administrativa deve abranger a API administrativa e a interface de organização, evitando interferência nas rotas públicas.
4. Verificar cache desabilitado para páginas e APIs com sessões ou tokens; segredos do convite são sensíveis.
5. Confirmar backup MySQL cifrado em armazenamento externo e restauração em banco isolado; registrar versão de esquema 006.
6. Testar Android e iPhone físicos: convite individual, clique opcional de interesse, recusa, confirmação, link de edição, internet instável e WhatsApp. Usar apenas famílias fictícias.
7. Confirmar CI verde no commit **exato** escolhido e ensaiar rollback antes de publicar. As PRs #12 e #13 já foram mescladas; exigir também [comparação de arquivos públicos](verificacao-versao-publicada.md) para identificar interface desatualizada, sem inferir a versão do backend.
8. Após aprovação, registrar data, versão/commit e evidências no checklist privado de liberação; somente então enviar convites reais.

## Registro de evidências (preencher com resultados reais)

| Verificação | Resultado | Evidência |
| --- | --- | --- |
| CI completa do SHA escolhido | Pendente | Link do run |
| Container + banco no policorp | Pendente | Sem segredos |
| Domínio, TLS e tunnel externo | Pendente | Teste de fora da rede |
| Preflight e check_production | Pendente | Saída sem dados pessoais |
| Backup cifrado + restauração isolada | Pendente | Registro interno |
| Android físico | Pendente | Checklist |
| iPhone físico | Pendente | Checklist |
| Aceite para envio real | Pendente | Aprovação explícita |

Relacionados: issues #14–#21, PRs #12 e #13 (já integradas), [CI #328 da main](https://github.com/jeffaxe81/axe-gestao-convites/actions/runs/42787828624).

## Conferência complementar da versão em execução

Após uma implantação controlada e **sem reiniciar nada apenas para diagnóstico**, execute `python scripts/check_deployed_revision.py --json`. Para exigir esse mesmo controle dentro do diagnóstico completo do host, selecione primeiro o SHA completo de um run verde na `main` e use `python scripts/diagnose_release.py --url https://isadora2anos.org --env-file .env --local-url http://127.0.0.1:8080 --require-local-gates --require-deployed-revision --expected-sha SHA_APROVADO_NA_CI --json` (substitua o marcador pelo commit real de 40 caracteres, não por `git rev-parse HEAD`). O modo `--expected-sha` também recusa checkout antigo, mesmo que seu rótulo Docker coincida consigo mesmo. A divergência impede o diagnóstico de seguir às verificações HTTPS públicas. O procedimento [Identidade da imagem Docker](identidade-imagem-deploy.md) descreve como etiquetar a imagem no build e verificar se o rótulo corresponde ao SHA do Git. Essa correlação não é prova criptográfica do backend, mas ajuda a detectar imagens antigas ou etiquetadas com revisão diferente. Imagens anteriores à mudança não possuem rótulo e serão sinalizadas como `BLOCKED`, sem afetar a execução.


## Validação independente da CI antes do diagnóstico local

Antes de aprovar o diagnóstico da instalação, obtenha **o SHA completo da `main` e o ID de sua execução verde mais recente** na página de Actions do GitHub. Não use um run de PR ou um SHA diferente do checkout. O verificador `scripts/check_green_main_ci.py` apenas lê a API pública do GitHub e compara a ponta atual da `main`, o SHA do workflow e seu resultado. Use os valores confirmados com `scripts/diagnose_release.py --expected-sha SHA_APROVADO --ci-run-id ID_RUN_VERDE --require-local-gates --require-deployed-revision --env-file .env --local-url http://127.0.0.1:8080 --url https://isadora2anos.org --json`.

A checagem da CI é **bloqueante em caso de indisponibilidade da API, divergência ou execução pendente/falha**; não realiza `git pull`, não envia dados do evento e não publica o aplicativo. Para detalhes do relatório, consulte [diagnóstico consolidado](diagnostico-consolidado.md). Ainda é obrigatório testar HTTPS a partir de outra rede, fazer backup/restore isolado no host e obter aceite.
