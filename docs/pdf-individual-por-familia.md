# PDF individual vinculado à família — Release 1

## Objetivo e limites

O convite real precisa usar o **link individual** emitido pelo painel `/organizar`: `https://isadora2anos.org/convite#UUID.TOKEN`.
O fragmento `#UUID.TOKEN` é uma credencial de acesso à família. **Não utilizar o PDF com a origem genérica do site para solicitar RSVP.** O botão e QR Code do PDF individual levam ao mesmo link secreto da família, sem pedir nome para localizar a lista.

O gerador é **offline**: não altera o MySQL, não registra envio, não envia mensagens, não habilita contatos reais e não substitui os seis comprovantes de homologação. Continuam bloqueadas a divulgação real e a declaração de 100% enquanto não houver aceite.

## Procedimento de homologação com família fictícia

1. No painel autenticado, em **Distribuição e acompanhamento dos convites**, selecione uma **família fictícia** importada e clique em **Copiar link**. Nunca compartilhe o CSV completo de links com convidados.
2. Escolha uma pasta privada **fora do Git**, com permissões restritas. Exemplo Linux: `mkdir -m 700 -p "$HOME/convites-privados"`.
3. No terminal, execute:

```bash
python scripts/generate_invitation.py \
  --family-link-stdin --check-production \
  --venue "Local confirmado" \
  --output "$HOME/convites-privados/convite-teste.pdf"
```

4. Quando solicitado, cole o link **individual**. A entrada interativa fica oculta; não passe o token como argumento de processo nem digite o segredo diretamente numa linha de comando para evitar histórico do shell. Para entrada por pipeline, o programa lê apenas a primeira linha.
5. O arquivo é criado com permissão `0600`, não sobrescreve outro PDF e não pode ser gravado dentro do repositório. QR Code e botão contêm a credencial familiar; o PDF deve ser tratado como privado.
6. Envie manualmente **apenas para aparelho de teste autorizado** e valide Android, iPhone, WhatsApp, QR, confirmação, recusa, edição e rede instável. Para produção, siga o aceite e as evidências humanas da [homologação](homologacao-policorp-cloudflare.md).

### Validações adicionais

- `--family-link-stdin` exige domínio público HTTPS sem porta e o caminho exato `/convite#UUIDv4.token-hexadecimal` com token de 64 caracteres. Links gerais, localhost, parâmetros de consulta, formato alterado ou token ausente são rejeitados.
- `--check-production` verifica **somente a origem HTTPS**, sem repassar token de família ao verificador. Isso não certifica a validade da família ou dos dados cadastrais, nem entrega da mensagem.
- `--url https://isadora2anos.org` produz um **modelo geral identificado como NÃO ENVIAR**, sem QR Code e sem links/ações PDF clicáveis. A origem HTTPS é validada, mas não aparece como link de confirmação. O modo `--preview` também permanece sem links. Somente `--family-link-stdin` habilita QR Code e botão com o link individual.
- A impressão, extração, encaminhamento ou captura do PDF expõe a credencial da família. Elimine arquivos de teste quando não necessários e não inclua PDFs nem links em issues, logs, anexos públicos ou Git.

## Critério de liberação

A Release 1 continua em **86% (6/7)** até completar DNS/HTTPS externo, backup/restauração real, Android físico, iPhone físico, segurança independente e aceite formal. A CI verde só valida o código em testes automatizados.
