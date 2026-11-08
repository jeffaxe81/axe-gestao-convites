# Domínio flexível — produto finalizado sem hospedagem

O domínio **não é exigido para concluir o Convites AXE**. O mesmo código funciona localmente e, depois, pode usar um domínio real via `APP_PUBLIC_URL` sem alterações no backend/frontend.

## Agora: sem domínio

Copie `.env.example` para `.env`, substitua todas as credenciais e segredos de demonstração por valores fortes e proteja o arquivo (`chmod 600 .env` em Linux). Execute:

```bash
python scripts/set_public_url.py --local
python scripts/preflight.py --env-file .env --local
docker compose up -d --build --wait
```

Acesse `http://127.0.0.1:8080` no próprio servidor. Modo local **não é publicação**.

## Depois: informar domínio e habilitar HTTPS

Quando houver servidor, DNS e proxy HTTPS/Cloudflare Tunnel configurados:

```bash
python scripts/set_public_url.py --domain convites.seudominio.com.br
python scripts/preflight.py --env-file .env
docker compose up -d --no-deps --force-recreate app
python scripts/check_production.py --url https://convites.seudominio.com.br
```

O configurador modifica somente `APP_PUBLIC_URL`, mantendo as demais configurações e segredos intactos; aceita também `https://convites.seudominio.com.br`. O reinício do serviço `app` aplica a mudança de cookie `Secure`, sem recriar banco ou modificar o projeto. DNS e certificado devem ser verificados separadamente.

O PDF final deve ser gerado **após** definir a URL porque o QR Code e o botão gravam o destino no arquivo:

```bash
python scripts/generate_invitation.py --url https://convites.seudominio.com.br --check-production --output /PASTA-PRIVADA/convite.pdf --venue "LOCAL_CONFIRMADO"
```

Ao trocar novamente de domínio, gere um novo PDF e atualize os convites conforme necessário. A publicação exige teste WhatsApp/Android/iPhone, backup externo e aceite de segurança, mas isso **não impede concluir o produto em código**.

## Segurança

- `--local` libera apenas loopback `127.0.0.1:8080` com pré-checagem local explícita.
- `--domain` exige HTTPS, hostname DNS válido, sem token, query, porta alternativa ou IP.
- O arquivo `.env` deve ser regular, privado (0600), sem links simbólicos ou entradas `APP_PUBLIC_URL` duplicadas.
- Não exponha a porta 8080 ou o banco MySQL diretamente à internet.
