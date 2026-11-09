# Interesse voluntário dos convidados

## Definição
A página de convite individual oferece o botão opcional **“💛 Gostei do convite”**. O clique autenticado pelo token privado cria um registro por família e um evento de auditoria sem dados pessoais. Atualizar ou reabrir a página não registra interesse por conta própria.

## Métricas no painel
O painel diferencia **famílias cadastradas**, **envio declarado manualmente**, **interesse voluntário**, **confirmadas**, **recusadas** e **pendentes**. Interesse é um sinal explícito de interação e não significa leitura integral, compreensão, entrega do WhatsApp ou presença confirmada. A contagem é por família e idempotente.

## API
`POST /api/invitations/{id}/interest` com `Authorization: Bearer <token-do-convite>` retorna `{"interested":true}`. A mesma credencial autoriza consultar o indicador booleano em `GET /api/invitations/{id}`. A API administrativa autenticada inclui `interested`, `interested_at_utc` e `counts.interested`.

## Segurança, implantação e privacidade
A migração aditiva 006 cria a tabela `invitation_interests`; nenhuma confirmação ou registro de envio existente é modificado. O evento não coleta IP, user-agent ou rastreio invisível. O token permanece no fragmento da URL e não é registrado em logs. O estado de interesse deve ser explicado aos convidados. Exigir CI verde e homologação em celular com dados fictícios antes da implantação. Não usar pixels invisíveis ou confundir clique com leitura comprovada.
