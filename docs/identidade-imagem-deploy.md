# Conferência do commit na imagem Docker em execução

## Motivo

A igualdade dos arquivos CSS/JavaScript públicos não demonstra qual código Python está dentro do contêiner. Para reduzir erros operacionais, o build da aplicação passa a receber uma **revisão declarada** (`SOURCE_REVISION`) e gravá-la no rótulo OCI `org.opencontainers.image.revision`.

O comando `scripts/check_deployed_revision.py` **somente lê** o SHA do checkout Git e o rótulo do contêiner `app`, exigindo que:
- o checkout esteja limpo e possua um SHA Git completo;
- exista exatamente um contêiner `app` identificável;
- o contêiner esteja em execução e com saúde `healthy`;
- o rótulo seja um SHA de 40 caracteres e corresponda ao checkout.

Este procedimento **não consulta a aplicação por dentro**, não examina os bytes da imagem, não verifica o DNS/Cloudflare nem autoriza distribuir convites. Uma etiqueta de imagem pode ser informada incorretamente na compilação; conferir também a origem da imagem e a CI do SHA.

## Na CI

A CI fornece `SOURCE_REVISION=${{ github.sha }}` à etapa de build e executa o verificador logo após `docker compose up -d --build --wait`. A checagem não modifica contêineres nem dados.

## No servidor policorp (somente depois de backup e planejamento)

**Não executar build, pull, rollback ou recriação do app automaticamente a partir de um diagnóstico.** Primeiro conferir volume MySQL, credenciais, janela de manutenção e rollback.

Uma implantação controlada futura, executada pelo responsável após a aprovação do plano, pode etiquetar o build assim:

```bash
cd ~/Projetos/jeffaxe81/axe-gestao-convites
git rev-parse HEAD
git status --short
# Somente após backup/rollback e autorização para atualizar o ambiente:
SOURCE_REVISION="$(git rev-parse HEAD)" docker compose up -d --build --wait
```

Depois, a consulta de leitura pode ser executada:

```bash
python scripts/check_deployed_revision.py --json
python scripts/diagnose_release.py \
  --url https://isadora2anos.org \
  --env-file .env --local-url http://127.0.0.1:8080 \
  --require-local-gates --json
```

O comando de conferência da revisão retorna `PASS` somente se a imagem em execução foi **etiquetada com o mesmo SHA** do checkout e o contêiner está saudável. Imagens antigas sem etiqueta retornarão `BLOCKED`; isso não significa que o aplicativo esteja fora do ar. Não alterar serviços apenas para silenciar este resultado.

Não use `docker compose down -v`, `docker volume prune`, nem imprima o conteúdo do `.env`.

## Interpretação e limites

- `revision_label_matches_checkout: true`: apenas a **identidade declarada** da imagem corresponde ao checkout local.
- `backend_code_proven: false`: não houve verificação byte a byte do backend; uma etiqueta não é prova criptográfica do conteúdo.
- `public_domain_verified: false`: esta ferramenta não consulta HTTPS público.
- `release_approved: false`: **sempre falso**. A autorização exige seis evidências humanas, inclusive testes Android/iPhone, backup/restauração real, revisão independente e aceite.

A CI no SHA, o diagnóstico HTTPS externo e as evidências privadas de homologação continuam obrigatórios. **Liberação operacional permanece em 86% (6/7)** até a aprovação real.
