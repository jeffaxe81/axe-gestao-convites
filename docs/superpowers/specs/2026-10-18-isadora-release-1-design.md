# Gestão de convites Isadora — especificação da release 1

Data: 18/10/2026.
Estado: especificação para revisão. Este documento não representa software implementado nem testes executados.
Repositório: jeffaxe81/axe-gestao-convites.

## Objetivo e escopo aprovado na conversa

Criar um aplicativo web para confirmar presença no aniversário de dois anos da Isadora e permitir aos organizadores acompanhar respostas, quantidade de participantes e lembrancinhas. A primeira release contém somente o fluxo e os controles abaixo. Ideias adicionais pertencem ao brainstorming da release 2.

O convite será produzido fora do aplicativo. O usuário colocará nele o endereço da página de confirmação e enviará o PDF pelo WhatsApp. A criação ou distribuição do convite não faz parte desta entrega.

## Festa e apresentação

- Evento: aniversário de dois anos da Isadora.
- Data e horário: domingo, 13/12/2026, às 15h, no fuso America/Sao_Paulo.
- Local ainda não definido: apresentar “Local a confirmar” e permitir atualizar essa informação posteriormente, mantendo o endereço da página.
- Visual delicado e infantil, com amarelo-manteiga, margaridas e composição harmônica.
- Página adaptada ao celular, com texto legível, contraste adequado, campos identificados e botões confortáveis para toque.
- Um endereço público estável para a confirmação. A escolha de domínio ou hospedagem não está implícita na criação do repositório.

## Página do convidado

1. Mostrar as informações da festa e as opções de comparecer ou não comparecer.
2. Pedir o nome também na resposta negativa, para que os organizadores saibam quem recusou.
3. Para confirmação positiva, registrar o nome do convidado e de cada acompanhante. O convidado principal também conta como participante, uma única vez.
4. Identificar cada participante como criança de zero a doze anos ou pessoa acima de doze. Para crianças, pedir a idade em anos completos no dia da festa, sem coletar data de nascimento.
5. Permitir revisar os nomes e a resposta antes de enviar.
6. Após gravação bem-sucedida, mostrar agradecimento e o resultado da confirmação.
7. Disponibilizar a edição daquela resposta até o prazo configurado. Atualizar o registro existente, sem criar uma nova família ou duplicar participantes.

A página pública e suas respostas de API não devem expor valores, regras de cobrança, classificação de participantes para o buffet, limite interno de quarenta, contagens globais, lista de outras famílias ou motivos financeiros da coleta de idade. Essas informações devem ser calculadas e consultadas apenas na área dos organizadores.

## Regras de contagem

Todas as contagens consideram somente participantes com presença confirmada.

| Idade no dia da festa | Entra na contagem do buffet | Entra na lista de lembrancinhas |
| --- | --- | --- |
| Zero a cinco anos, inclusive | Não | Sim |
| Seis a doze anos, inclusive | Sim | Sim |
| Acima de doze anos | Sim | Não |

- O limite de quarenta considera apenas pessoas incluídas na contagem do buffet.
- Crianças até cinco anos são contabilizadas separadamente e não consomem esse limite.
- A lista de lembrancinhas inclui os nomes e o total de todas as crianças de zero a doze anos, inclusive.
- O painel também mostra o total geral de confirmados e, separadamente, crianças de zero a doze e participantes acima de doze.
- Uma criança de oito anos participa tanto da contagem do buffet quanto da lista de lembrancinhas.
- Recusas não entram em nenhuma contagem de presença, buffet ou lembrancinhas.
- Editar acompanhantes, idades ou presença recalcula os totais a partir dos registros atuais.

## Painel privado dos organizadores

- Acesso autenticado, com credenciais protegidas.
- Listas separadas de confirmações e recusas.
- Visualização dos nomes e acompanhantes vinculados a cada resposta.
- Contadores definidos acima e lista nominal de crianças para lembrancinhas.
- Configuração do local e da data e horário limite para edição.
- Controles e dados de buffet disponíveis exclusivamente aos organizadores.

Não haverá lista de “quem ainda não respondeu” nesta versão, pois não foi solicitado um cadastro prévio de todos os convidados.

## Prazo de edição e identificação da resposta

O prazo será definido posteriormente pelo usuário, sem impedir o início do projeto. Enquanto não estiver configurado, a edição permanece aberta. Quando houver prazo, uma alteração será aceita somente antes do instante limite, considerando o fuso da festa. No instante limite e depois dele, a edição pelo convidado será encerrada. O servidor é responsável por validar a regra.

Decisões técnicas propostas para revisão:
- Cada resposta terá um link privado de edição, com segredo aleatório, para permitir acesso à própria confirmação sem exigir criação de conta.
- O nome de uma pessoa não será usado como senha nem como identificador único. Homônimos não serão descartados automaticamente.
- O prazo configurado limita a edição; encerramento de novas confirmações não foi solicitado.
- O limite de quarenta será apresentado como contador e alerta interno aos organizadores. Não haverá bloqueio automático de convidados nem exposição desse limite na página pública.

## Arquitetura e Docker

- Aplicação web com página pública, painel autenticado e API no mesmo serviço de aplicação.
- Banco de dados MySQL, conforme escolha expressa do usuário.
- Docker Compose com dois serviços: aplicação e MySQL.
- Dados do MySQL em volume persistente, preservados ao recriar o contêiner da aplicação.
- Banco acessível pela aplicação na rede interna do Compose; publicação da porta do banco não é necessária para o uso normal.
- Configuração por ambiente, com arquivo de exemplo sem credenciais reais.
- Inicialização documentada, migrações de esquema e verificações de saúde.
- Separação entre ambiente real e banco de testes.

Estrutura mínima de dados: configuração do evento, respostas e participantes. Dados de autenticação e segredos de configuração serão protegidos e não integrarão o repositório. Alterações de uma resposta e de seus participantes devem ocorrer em uma transação.

## Estratégia de testes exigida para a release

Os testes abaixo serão implementados junto com o código. Não foram executados neste estágio de especificação.

### Regras de negócio

- Idades de fronteira: zero, cinco, seis, doze e treze anos.
- Soma do buffet, crianças até cinco, crianças até doze e total geral.
- Confirmação positiva e negativa, alterações de idade, inclusão e remoção de acompanhantes.
- Troca de confirmação positiva para recusa, retirando toda a resposta das contagens de presença.
- Sequências variadas de edições, verificando os totais por recálculo independente dos registros.
- Rejeição de nomes vazios e idades infantis negativas, fracionárias ou fora da faixa permitida.

### API, banco e concorrência

- Integração com MySQL real, em ambiente de teste isolado.
- Transações: falha ao salvar acompanhantes não deixa uma resposta parcialmente atualizada.
- Reenvio da mesma operação, duplo clique e repetição após falha de rede não duplicam registros.
- Edição usa a mesma resposta; submissões e edições simultâneas não perdem participantes nem corrompem totais.
- Contagem interna correta ao atingir e ultrapassar quarenta, conforme a política de alerta proposta.
- Tratamento de indisponibilidade do banco, sem apresentar confirmação de sucesso antes da persistência.

### Prazo e autorização

- Edição com prazo não configurado e com prazo configurado.
- Instantes imediatamente antes, exatamente no limite e depois do limite.
- Conversão entre o fuso da festa e a representação persistida.
- Uma família não consegue consultar ou alterar a resposta de outra.
- Segredos inválidos, ausentes ou expirados e tentativas de alteração após o prazo.
- Área privada e operações de configuração indisponíveis para convidados.

### Privacidade e segurança

- Inspeção das respostas públicas e do conteúdo entregue ao navegador para verificar ausência de dados financeiros e listas privadas.
- Nomes tratados como texto, sem execução de HTML ou scripts.
- Consultas ao banco parametrizadas.
- Proteção de sessão e de operações autenticadas contra requisições indevidas.
- Segredos e dados pessoais ausentes de logs desnecessários, mensagens de erro e arquivos versionados.
- Controles contra submissões automatizadas excessivas, sem adicionar cadastro de usuário ao convidado.

### Fluxo completo e operação

- Testes de navegador do fluxo positivo, negativo e de edição, incluindo formulário de acompanhantes e visualização em celular.
- Verificação do painel com um conjunto conhecido de famílias e idades.
- Contêineres iniciam pelo Compose, verificações de saúde respondem e as migrações são aplicadas.
- Recriação dos contêineres preserva as respostas no volume.
- Checklist manual em Android e iPhone: abertura do link pelo PDF recebido no WhatsApp, navegação, teclado, legibilidade e agradecimento.
- Evidências de testes, comandos executados e limitações do ambiente acompanham a entrega. Uma etapa não executada será identificada como pendente de validação, sem alegação de aprovação.

## Critérios para concluir a release 1

1. Fluxos de confirmação, recusa e edição funcionam conforme esta especificação.
2. As listas e os totais coincidem com os dados de teste, inclusive nas fronteiras de idade.
3. Informações internas do buffet permanecem restritas ao painel autenticado.
4. O prazo é configurável e validado no servidor.
5. A instalação em Docker com MySQL e persistência está documentada e validada.
6. Os testes automatizados previstos possuem resultados verificáveis, e o checklist manual identifica o que foi efetivamente conferido.
7. Nenhuma funcionalidade da release 2 foi incluída nesta entrega.

## Etapas de execução

1. Revisar esta especificação, especialmente as decisões técnicas propostas.
2. Detalhar o plano técnico de implementação e os comandos de validação.
3. Implementar banco, API, página pública e painel, com testes acompanhando as regras.
4. Validar integração, navegador, concorrência e instalação em Docker.
5. Entregar código, instruções de execução e evidências de validação.
6. Depois da primeira entrega, iniciar um brainstorming separado para a release 2.
