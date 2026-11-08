# Segurança para publicação — Release 1 Isadora

Esta documentação **não** é um certificado de segurança nem uma autorização para expor o serviço. O código continua em PR rascunho.

## Proteções implementadas e testadas no CI

- A aplicação não inicia com URL pública HTTP, exceto em `localhost`, `127.0.0.1` ou `::1`.
- Docker Compose publica a porta 8080 somente em `127.0.0.1`. Usuários externos não devem acessá-la diretamente.
- Cookies de sessão administrativa são `HttpOnly`, `SameSite=Lax` e `Secure` quando o endereço externo é HTTPS; prazo da sessão: até 8 horas.
- Respostas HTML/JSON usam `Cache-Control: no-store`. CSP limita scripts e estilos à própria origem, impede `object`, `base` e incorporações em iframe. Cabeçalhos de clickjacking e privacidade ativados.
- Contadores financeiros e famílias alheias permanecem fora das APIs públicas.
- O limitador de requisições não aceita `X-Forwarded-For` por padrão. Aceita somente **um** proxy confiável quando `TRUSTED_PROXY_HOPS=1` é configurado.
- GitHub Actions com 84 testes e ensaio Docker: https://github.com/jeffaxe81/axe-gestao-convites/actions/runs/39175630043

## Publicação recomendada (ainda não executada)

1. Providenciar domínio real, servidor e certificado TLS válido. Configurar `APP_PUBLIC_URL=https://<dominio-real>` no arquivo privado `.env` (substituindo por domínio escolhido).
2. Manter o Docker Compose como fornecido, com `127.0.0.1:8080:8080`. Um Nginx/Caddy no mesmo host recebe HTTPS 443 e encaminha para `http://127.0.0.1:8080`.
3. No proxy, rejeitar HTTP externo ou redirecionar para HTTPS; configurar HSTS, limite de corpo/timeout e cabeçalhos seguros.
4. Apenas se o proxy estiver no mesmo host e controlar a origem, configurar `TRUSTED_PROXY_HOPS=1`. O proxy **deve substituir** o cabeçalho `X-Forwarded-For` pelo IP remoto validado, nunca usar cegamente um valor informado pelo visitante. Caso contrário, manter 0.
5. Configurar rate limit centralizado no proxy/WAF. O limitador em memória do Flask atua por trabalhador Gunicorn e não oferece cota global compartilhada.
6. Definir segredos aleatórios fortes, hash de senha administrativo, backups cifrados, teste de restauração, retenção e política de eliminação de dados pessoais. Não versionar nomes, tokens ou arquivos `.env`.
7. Inspecionar certificados, HTTPS efetivo, flags de cookies, ausência de dados internos no código e respostas públicas, logs e backup.
8. Executar os testes manuais de Android/iPhone listados em `docs/manual-checklist.md`, incluindo link enviado no PDF via WhatsApp e envio com perda de rede.
9. Solicitar revisão técnica independente, documentar aceite e só então divulgar o link.

## Riscos e limites ainda abertos

- Não há hospedagem pública, DNS ou HTTPS implantados. Os testes passaram em CI, não em servidor final.
- Não houve ensaio em Android ou iPhone físicos, nem abertura real pelo PDF no WhatsApp.
- Rate limit local em memória não é mecanismo distribuído contra ataques.
- Sessões administrativas são assinadas no cliente; o logout remove o cookie atual, mas não revoga uma cópia já furtada. É necessário controlar acesso, evitar vazamento de sessão e ter processo de rotação do segredo.
- Política formal de retenção, restauração e descarte de dados pessoais ainda depende do operador.
- Auditoria externa de segurança e homologação final ainda pendentes.

**Decisão operacional:** manter a Release 1 em rascunho e barra de progresso em 86% até finalizar a etapa de validação e aprovação real.
