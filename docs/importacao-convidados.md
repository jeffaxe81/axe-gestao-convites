# Lista inicial de convidados e links individuais

## Objetivo
Permitir que o organizador importe famílias antes do envio dos convites, gere um link exclusivo por família e acompanhe o andamento sem criar confirmações fictícias.

## Planilha CSV
Arquivo de exemplo: `docs/modelo_lista_convidados.csv`.

Colunas obrigatórias:
- `Nome da família`: identificação administrativa da família.
- `Responsável`: nome da pessoa de contato.
- `WhatsApp`: país + DDD + número, somente dígitos (ex.: 5548999991111).
- `Convidados`: quantidade prevista para planejamento, não é limite de confirmação.

Uma linha representa uma família. Não inserir cabeçalhos extras, fórmulas ou linhas de totalização. Salvar em CSV UTF-8.

## Regras funcionais
1. Importar em modo de pré-validação e mostrar erros por linha antes de gravar.
2. Não criar registros na tabela de confirmações (`families`) durante a importação.
3. Gerar token criptograficamente aleatório por família; persistir somente hash do token. O link usa fragmento da URL (/#convite=...) para não enviar o token nos logs HTTP.
4. Link de convite deve abrir o formulário público com contexto da família.
5. No envio do RSVP, associar a resposta ao convite e impedir reutilização indevida.
6. Quantidade prevista é informativa; o RSVP permanece com a regra atual de até 100 participantes, sem bloquear acima/abaixo da previsão.
7. Estados administrativos: Pendente, Link gerado, Enviado, Confirmado, Recusado.
8. Não marcar como enviado apenas por abrir WhatsApp; permitir confirmação manual de envio.
9. Permitir revogar e regenerar link, invalidando o anterior.
10. Proteger importação, listagem, exportação e ações com sessão administrativa e CSRF.

## Segurança e privacidade
- Não colocar tokens em logs, relatórios públicos ou histórico de auditoria.
- Não expor telefone ou nomes em endpoints públicos.
- Validar CSV por tamanho, número de linhas, cabeçalhos e conteúdo.
- Escapar conteúdo ao exibir nomes no painel.
- Preservar integralmente confirmações já existentes.
- Nunca apagar ou recriar o volume MySQL para aplicar migrações.

## Plano de entrega em 20 frentes
1. Modelo relacional de convites.
2. Migração aditiva e reversível operacionalmente.
3. Serviço de geração e hash de tokens.
4. Pré-validação CSV.
5. Importação transacional.
6. Detecção de duplicidade de telefone/família.
7. Listagem e pesquisa administrativa.
8. Página de convite individual.
9. Contexto de convite no formulário público.
10. Associação do RSVP ao convite.
11. Proteção contra reutilização de token.
12. Revogação e regeneração.
13. Mensagem WhatsApp pré-preenchida.
14. Controle manual de envio.
15. Estados e indicadores.
16. Exportação CSV administrativa.
17. Proteção CSRF e autorização.
18. Auditoria sem dados pessoais.
19. Testes unitários, integração e regressão.
20. Documentação, build Docker e homologação.

## Critérios de aceite
- Importar CSV válido sem gerar RSVP; os links puros são exibidos uma única vez e podem ser baixados imediatamente em CSV.
- CSV inválido apresenta erros por linha sem importação parcial.
- Cada família recebe link exclusivo e revogável.
- RSVP pelo link fica associado à família correta.
- RSVP direto atual continua funcionando.
- Nenhum dado histórico é perdido ou alterado.
- Testes e health check passam antes de publicar.
