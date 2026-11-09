# Cadastro prévio de famílias (Excel ou CSV)

Acesse `/organizar`, faça login e procure **Lista de famílias — preparar planilha**.

1. Baixe o modelo CSV e abra no Excel ou em um editor de planilhas.
2. Preencha uma linha para cada família. Os nomes das colunas devem permanecer iguais e na ordem especificada.
3. Salve como CSV UTF-8 separado por ponto e vírgula ou arquivo Excel .xlsx; apenas a primeira aba é considerada.
4. Envie o arquivo e clique em **Validar planilha**. O servidor não grava cadastros nesta etapa.
5. Depois de revisar os totais, clique em **Confirmar cadastro prévio** para gravar os registros no MySQL.

| familia | responsavel | telefone | adultos | criancas_0_5 | criancas_6_12 |
|---|---|---|---|---|---|
| familia-silva | Maria Silva | 11999999999 | 2 | 1 | 0 |

O exemplo acima é fictício e deve ser removido antes de importar convidados reais.

**Comportamento:** máximo de 500 famílias e arquivo de até 60 KB. O campo `familia` é um código estável e único, de 3 a 64 caracteres ASCII (letras, dígitos, hífen, sublinhado). Telefone é opcional, com 10 a 15 dígitos e `+` inicial opcional. Adultos e cada faixa de crianças aceitam de 0 a 30; a família precisa de pelo menos uma pessoa.

A importação é transacional e idempotente: repetir a mesma planilha mantém cadastros; alterar dados de uma família já cadastrada provoca erro e não importa nenhuma linha daquela operação. Nenhum convidado importado é contabilizado como confirmação; as famílias permanecem em estado `PENDING`.

**Segurança:** exigir autenticação de organizador e token CSRF; nunca guardar a planilha original no servidor ou divulgar listas nominalmente na API pública. Arquivos XLSX com fórmulas não são aceitos. Não publicar links individuais ou disparar WhatsApp nesta entrega.

## Links individuais e respostas vinculadas

Depois de importar as famílias, clique em **Exportar links individuais (CSV)**. O arquivo traz uma linha por família com código, responsável, telefone, situação e link secreto. A geração usa a URL configurada em `APP_PUBLIC_URL`; para compartilhar, use o domínio HTTPS homologado, nunca endereços localhost. O envio por WhatsApp continua manual.

Cada link tem o formato `https://seu-dominio/convite#id.token`. O identificador e o segredo ficam no fragmento, que o navegador não envia nas requisições HTTP. A página solicita apenas os dados autorizados daquela família e mostra quantidades previstas da planilha, sem inseri-las como confirmações. O convidado informa nomes e idades reais antes de enviar.

A resposta é criada transacionalmente, associada ao cadastro importado e registrada uma única vez. Uma tentativa idêntica de reenvio retorna o mesmo comprovante (idempotência). Para alterar os dados, o convidado utiliza o link privado de edição apresentado após a confirmação; o link original também permite recuperar esse comprovante. O painel de convites distingue `PENDENTE`, `CONFIRMADO` e `RECUSADO`; os indicadores de buffet usam exclusivamente participantes efetivamente confirmados.

**Confidencialidade:** o arquivo `links-individuais-familias.csv` contém credenciais de acesso à confirmação. Trate como secreto, não carregue em serviços públicos nem distribua o arquivo inteiro para convidados. Somente o organizador autenticado pode exportá-lo. A posse do link de família permite consultar seu cadastro e enviar ou recuperar sua resposta.

**Limitações atuais:** não há edição/exclusão administrativa de famílias importadas nem disparo automatizado por WhatsApp. Os campos de adultos e crianças da planilha são quantidades planejadas, não nomes e idades individuais; a confirmação solicita os nomes reais. A disponibilidade do domínio e o recebimento em celulares reais ainda precisam ser homologados antes de envio aos convidados.
