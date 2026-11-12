# Cadastro prévio de famílias (Excel ou CSV)

Acesse `/organizar`, faça login e procure **Lista de famílias — preparar planilha**.

1. Baixe o modelo **CSV ou Excel (.xlsx)** diretamente no painel. Ambos incluem uma linha fictícia de exemplo.
2. Substitua a linha fictícia por seus próprios dados e preencha uma linha para cada família. Os nomes das colunas devem permanecer iguais e na ordem especificada.
3. Salve como CSV UTF-8 separado por ponto e vírgula ou arquivo Excel .xlsx. No Excel, **somente a primeira aba na ordem mostrada pelo arquivo** será importada, mesmo que ela esteja armazenada internamente como `sheet2.xml` ou outro nome. Deixe a aba desejada na primeira posição e visível.
4. Envie o arquivo e clique em **Validar planilha**. O servidor não grava cadastros nesta etapa.
5. Depois de revisar os totais, clique em **Confirmar cadastro prévio** para gravar os registros no MySQL.

| familia | responsavel | telefone | adultos | criancas_0_5 | criancas_6_12 |
|---|---|---|---|---|---|
| familia-silva | Maria Silva | 11999999999 | 2 | 1 | 0 |

O exemplo acima é fictício e deve ser removido antes de importar convidados reais.

**Comportamento:** máximo de 500 famílias e arquivo de até 60 KB. O campo `familia` é um código estável e único, de 3 a 64 caracteres ASCII (letras, dígitos, hífen, sublinhado). Telefone é opcional, com 10 a 15 dígitos e `+` inicial opcional. Adultos e cada faixa de crianças aceitam de 0 a 30; a família precisa de pelo menos uma pessoa.

A importação é transacional e idempotente: repetir a mesma planilha mantém cadastros; alterar dados de uma família já cadastrada provoca erro e não importa nenhuma linha daquela operação. Nenhum convidado importado é contabilizado como confirmação; as famílias permanecem em estado `PENDING`.

**Segurança:** exigir autenticação de organizador e token CSRF; nunca guardar a planilha original no servidor ou divulgar listas nominalmente na API pública. Arquivos XLSX com fórmulas não são aceitos. Planilhas sem o catálogo de abas e relacionamentos internos válidos, com primeira aba oculta ou com relação externa também são recusadas. **Antes de importar, reexiba todas as linhas da primeira aba e as colunas A a F**: linhas/colunas ocultas, linhas fora de ordem e células duplicadas ou fora da linha correspondente são recusadas para evitar importar contatos invisíveis ou ambíguos. Filtros do Excel podem ocultar linhas; limpe os filtros e reexiba os dados. O sistema não executa links nem fórmulas embutidos no Excel. Não publicar links individuais ou disparar WhatsApp nesta entrega.

## Links individuais e respostas vinculadas

**Controle de acesso em produção:** novas confirmações são aceitas somente pelo link individual de família pré-cadastrada. A página inicial `/` informa como obter o link e não exibe formulário anônimo. A rota antiga `POST /api/rsvps` responde `403 INVITATION_REQUIRED` antes de gravar dados; os links de edição de confirmações anteriores continuam válidos. A rota autenticada por token de família `/api/invitations/<id>/response` permanece funcional e idempotente. O modo de testes isolados mantém o fluxo legado para regressão, mas não é configurável para desativar a proteção em produção.

Depois de importar as famílias, clique em **Exportar links individuais (CSV)**. O arquivo traz uma linha por família com código, responsável, telefone, situação e link secreto. A geração usa a URL configurada em `APP_PUBLIC_URL`; para compartilhar, use o domínio HTTPS homologado, nunca endereços localhost. O envio por WhatsApp continua manual.

Cada link tem o formato `https://seu-dominio/convite#id.token`. O identificador e o segredo ficam no fragmento, que o navegador não envia nas requisições HTTP. A página solicita apenas os dados autorizados daquela família e mostra quantidades previstas da planilha, sem inseri-las como confirmações. O convidado informa nomes e idades reais antes de enviar.

A resposta é criada transacionalmente, associada ao cadastro importado e registrada uma única vez. Uma tentativa idêntica de reenvio retorna o mesmo comprovante (idempotência). Para alterar os dados, o convidado utiliza o link privado de edição apresentado após a confirmação; o link original também permite recuperar esse comprovante. O painel de convites distingue `PENDENTE`, `CONFIRMADO` e `RECUSADO`; os indicadores de buffet usam exclusivamente participantes efetivamente confirmados.

**Confidencialidade:** o arquivo `links-individuais-familias.csv` contém credenciais de acesso à confirmação. Trate como secreto, não carregue em serviços públicos nem distribua o arquivo inteiro para convidados. Somente o organizador autenticado pode exportá-lo. A posse do link de família permite consultar seu cadastro e enviar ou recuperar sua resposta.

**Limitações atuais:** não há edição/exclusão administrativa de famílias importadas nem disparo automatizado por WhatsApp. Os campos de adultos e crianças da planilha são quantidades planejadas, não nomes e idades individuais; a confirmação solicita os nomes reais. A disponibilidade do domínio e o recebimento em celulares reais ainda precisam ser homologados antes de envio aos convidados.

## Distribuição manual e acompanhamento pelo painel

Na área `/organizar`, seção **Distribuição e acompanhamento dos convites**:

- Os indicadores mostram famílias **cadastradas**, **aguardando resposta**, **confirmadas** e **recusadas**. O estado é atualizado a partir dos registros de RSVP, inclusive após a edição da resposta.
- Pesquise por nome, código da família ou telefone. O filtro de situação não altera a base.
- **Copiar link** solicita somente o endereço daquela família após o clique. Se o navegador bloquear a área de transferência, o link aparece selecionado para cópia manual.
- **Preparar WhatsApp** exige telefone válido e origem pública HTTPS. O painel monta uma conversa individual com mensagem pré-preenchida e só depois mostra **Abrir conversa no WhatsApp**. Essa ação não envia mensagens, não comprova entrega e não altera status.
- Números brasileiros de 10 ou 11 dígitos são tratados como Brasil (+55); números internacionais exigem sinal `+` e código do país. Confira manualmente o destinatário antes de enviar.
- Dados pessoais e links são limpos da tela ao sair. A lista de acompanhamento não contém tokens; cada link secreto é recuperado separadamente sob autenticação.

**Operação segura:** somente usar os botões com famílias fictícias durante homologação. O botão WhatsApp pode revelar à plataforma de mensagens o texto e o link individual escolhido. Não acessar links privados em navegadores públicos, não salvar planilhas de distribuição em locais compartilhados, e nunca interpretar abrir uma conversa como envio concluído.

A exportação geral CSV continua disponível, mas reúne todas as credenciais de convite num único arquivo. Para rotina diária, prefira compartilhar pelo botão individual.

## Controle manual de envio — migração 005

O aplicativo armazena **dois estados independentes** para cada família:

- **Confirmação:** `PENDENTE`, `CONFIRMADO` ou `RECUSADO`, atualizado apenas pela resposta da família.
- **Envio manual:** `não registrado` ou `registrado como enviado`, com data e hora da declaração feita pelo organizador.

Na seção **Distribuição e acompanhamento**, pressione **Marcar como enviado manualmente** *somente após realmente compartilhar a mensagem com a família*. O ato de copiar link, preparar uma conversa ou abrir o WhatsApp não altera o registro.

Caso a marcação tenha sido feita por engano, pressione **Desfazer envio registrado**. Ambas as ações são auditadas sem guardar nomes, telefone nem link secreto. Repetir a mesma marcação não cria histórico duplicado nem modifica a data anterior.

Os indicadores de envio registrado / não registrado e o filtro correspondente não alteram contagem de convidados, buffet ou situação do RSVP. Uma recusa pode permanecer marcada como envio registrado, pois são fatos diferentes.

**Atenção:** o registro manual não é recibo de entrega, leitura ou envio automatizado pela API do WhatsApp. Não há integração com WhatsApp Business API ou confirmação técnica de entrega nesta versão. Para homologação, usar famílias e telefones fictícios no navegador e testar em dispositivos Android/iOS reais antes de liberar em produção.

## PDF individual com QR Code por família

Para a homologação com famílias fictícias, o script `scripts/generate_invitation.py` permite usar o **link individual** copiado do painel via `--family-link-stdin`, sem registrar o token nos argumentos do processo. O PDF gerado traz o link daquela família no QR Code e botão. A execução continua offline e **não marca como enviado**.

Consulte o procedimento [PDF individual vinculado à família](pdf-individual-por-familia.md). O modo antigo `--url` é apenas modelo geral, explicitamente rotulado **NÃO ENVIAR**, não um RSVP ligado à lista de convidados. O envio de convites reais depende da homologação física e aceite.
