# Publicação via Cloudflare Tunnel (opção de implantação)

**Não executado em produção.** Cloudflare Tunnel facilita publicar o site com HTTPS sem abrir portas inbound no firewall. O túnel **não substitui** revisão de segurança, backup externo ou testes físicos Android/iPhone.

Fontes oficiais (consultadas em outubro/2026):
- https://developers.cloudflare.com/tunnel/get-started/
- https://developers.cloudflare.com/tunnel/reference/tunnel-tokens/
- https://developers.cloudflare.com/tunnel/concepts/routing/

## Preparação no servidor (Linux)

1. Providencie domínio próprio associado à Cloudflare e servidor com Docker Compose, MySQL em volume persistente e conexão de saída para Cloudflare (normalmente porta 7844).
2. Defina \`APP_PUBLIC_URL=https://<subdomínio-do-seu-domínio>\` no .env **privado**. Configure demais segredos e hash de senha; execute \`chmod 600 .env\` e \`python scripts/preflight.py --env-file .env\`.
3. Inicie \`docker compose up -d --build --wait\`; confirme \`curl -fsS http://127.0.0.1:8080/health/ready\`. A aplicação permanece acessível somente em loopback: **nunca** troque para \`0.0.0.0:8080\`, nem exponha MySQL.
4. Na Cloudflare, abra **Networking > Tunnels > Create Tunnel**, crie um túnel gerenciado pelo painel e instale \`cloudflared\` **no mesmo host** como serviço usando o comando fornecido no painel. O token é segredo com capacidade de executar o túnel: não o coloque no Git, nos logs ou nesta conversa.
5. Dentro do túnel, **Routes > Add route > Published application**: hostname \`<subdomínio-do-seu-domínio>\`, service URL \`http://localhost:8080\`. A Cloudflare cria/associa o registro DNS do hostname.
6. Inicialmente mantenha \`TRUSTED_PROXY_HOPS=0\`, pois confiar incorretamente no X-Forwarded-For permite contornar limites de requisição. **Atenção:** com \`0\`, todos os convidados que chegam pelo mesmo conector podem compartilhar o limite em memória da aplicação. Configure WAF/rate limiting na Cloudflare e teste concorrência; só habilite \`1\` após comprovar que o proxy local reescreve os cabeçalhos de origem, sem permitir spoofing.
7. Configure HSTS na resposta pública HTTPS e regras para não fazer cache das rotas \`/\`, \`/editar\`, \`/organizar\`, \`/api/*\` e \`/health/*\`; não permita conteúdo personalizado em cache compartilhado. A verificação do projeto exige HSTS. Mantenha controle administrativo adicional (por exemplo, política de acesso por identidade para a área do organizador), sem impedir o formulário público de RSVP. Revise cuidadosamente os caminhos das APIs antes de restringir.
8. Execute de fora do host \`python scripts/check_production.py --url https://<subdomínio-do-seu-domínio>\`. Ele não cria convites; verifica TLS, cabeçalhos, privacidade e cookie.
9. Valide em Android e iPhone reais o QR Code e o botão do PDF recebido via WhatsApp; teste confirmação, recusa, edição e perda de rede. Faça backup cifrado externo, teste de restauração **no ambiente final** e registre retenção.
10. Somente depois do aceite técnico, gere o PDF definitivo e distribua os convites.

## Proteções e limites

- O túnel cria conexão **de saída** e não exige publicar portas 80/443 do servidor de origem. Uma aplicação exposta no hostname continua pública; o túnel não autentica convidados automaticamente.
- Prefira um túnel de produção gerenciado pelo painel em vez de Quick Tunnel temporário. Um link temporário não é adequado para PDF enviado a convidados.
- Nunca copie token de túnel, senhas de MySQL, \`SESSION_SECRET\`, \`TOKEN_SECRET\`, cookies ou links privados de edição em repositórios ou chats.
- Se não houver domínio próprio ou acesso ao servidor, esta etapa não pode ser concluída automaticamente.
