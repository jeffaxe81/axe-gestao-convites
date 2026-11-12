# Evidências privadas de homologação — policorp

Este procedimento **não executa implantação**. Ele registra, em um arquivo
privado, o resultado dos verificadores de leitura já existentes: revisão Git,
execução verde na `main`, configuração local (sem mostrar os segredos),
HTTP loopback, imagem Docker saudável, HTTPS público e assets publicados.

O coletor **não** faz login administrativo, não consulta famílias, não envia
RSVP/WhatsApp, não altera bancos nem contêineres. A única escrita é a criação
de um arquivo JSON novo, com permissão `0600`, em diretório privado `0700`
fora do checkout. Nenhum resultado substitui os seis comprovantes finais.

## Antes do comando

No servidor `policorp`, confirme que o checkout foi atualizado em procedimento
de implantação autorizado e que o serviço já está ativo. **Não execute
`git pull`, `docker compose up`, mudanças de senha ou migrações apenas para
gerar o relatório.** Obtenha na página GitHub Actions o SHA completo de 40
caracteres da `main` e o ID de sua execução verde **no mesmo commit**.

Crie a pasta privada uma única vez, com permissões corretas:

```bash
mkdir -p "$HOME/isadora-evidencias"
chmod 700 "$HOME/isadora-evidencias"
cd ~/Projetos/jeffaxe81/axe-gestao-convites
git status --short
```

Se o checkout estiver sujo, resolva a causa primeiro: o diagnóstico será
bloqueado. Nunca copie senhas, hashes administrativos, `.env`, links de
famílias ou conteúdo de backup para o relatório.

## Coleta somente de diagnóstico automatizado

Substitua os dois valores abaixo pelos valores reais e atuais de uma
**CI verde na `main`**. O exemplo de saída é um caminho **novo**: execute
novamente com outro nome, pois a ferramenta se recusa a sobrescrever.

```bash
SHA_APROVADO="<SHA_COMPLETO_DA_MAIN>"
RUN_APROVADO="<ID_DA_CI_VERDE_NESSE_SHA>"

python scripts/collect_host_evidence.py \
  --expected-sha "$SHA_APROVADO" \
  --ci-run-id "$RUN_APROVADO" \
  --output "$HOME/isadora-evidencias/diagnostico-rodada-01.json" \
  --json
```

O script exige o modo host estrito com `--require-local-gates` e
`--require-deployed-revision` internamente, usa `.env` apenas para validar
configuração, e consulta HTTPS com TLS válido. Se o servidor usa outro
endereço loopback, há o parâmetro `--local-url`; para proxy com
`TRUSTED_PROXY_HOPS=1`, só use `--allow-proxy-hop` após auditoria de seus
cabeçalhos.

O arquivo contém **somente campos permitidos**: estado dos gates, SHA da
versão, ID da CI, horário UTC e identificadores de verificações pendentes.
Não inclui erro bruto de rede, headers, nomes, links, tokens ou valores
de configuração. O arquivo é um **registro gerado pelo próprio host** e
não representa assinatura digital independente.

- Exit `0`: gates automatizados estritos passaram, mas o relatório declara
  `release_approved=false`.
- Exit `1`: diagnóstico bloqueado; registra os gates com falha, sem tentar
  corrigir o host.
- Exit `2`: saída inválida/insegura ou falha na criação do arquivo; não
  sobrescreve evidências existentes.

Se a pasta for acessível por outros usuários, o script bloqueia a criação.
Não grave o JSON dentro do repositório ou em diretório público.

## Evidências independentes (não automatizadas)

As seis verificações finais precisam ser executadas e registradas
**separadamente**, em repositório privado de evidências do operador:

1. DNS/TLS/Cloudflare: acesso de rede externa ao `isadora2anos.org`,
   com data, rede utilizada e resultado do diagnóstico HTTPS.
2. Backup cifrado externo: cópia protegida e ensaio de restauração em banco
   isolado na infraestrutura final, sem afetar a produção.
3. Android físico: família fictícia, PDF individual, WhatsApp, confirmação,
   recusa e link de edição em aparelho real.
4. iPhone físico: o mesmo ensaio, incluindo queda e retorno da conexão.
5. Revisão independente de segurança, com aceite dos achados resolvidos.
6. Autorização expressa do organizador **posterior** às outras cinco provas.

Após realizar esses ensaios, o operador registra referências privadas e datas
no manifesto do modelo `docs/release-evidence-template.json`, mantido **fora
do Git**, e executa `python scripts/release_readiness.py --evidence-file
/CAMINHO/PRIVADO/evidencias-humanas.json`. O verificador apenas confere a
integridade dos registros declarados: **não autentica seu conteúdo** e não
libera automaticamente o envio de convites.

**Situação da Release 1:** 100% de critérios técnicos (10/10), mas apenas
86% de liberação operacional (6/7) até a homologação real. Não enviar
convites reais antes do aceite formal.
