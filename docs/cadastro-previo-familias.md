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

**Limitações atuais:** esta etapa não oferece edição de cadastros importados, exclusão, convites por família, geração de links ou envio automático. Os campos de adultos e crianças são quantidades planejadas; não contêm os nomes e idades individuais que a confirmação definitiva solicitará. O processo de emissão de links e confirmação vinculada ao registro prévio exige etapa específica e homologação.
