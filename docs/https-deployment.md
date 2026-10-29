# Publicação HTTPS — Isadora Release 1

**Este roteiro ainda não foi executado em hospedagem definitiva.** Não divulgar o link aos convidados sem checklist de segurança e testes em Android/iPhone reais.

## Condições

- Domínio/subdomínio controlado pelo organizador, DNS apontando para um servidor, e portas TCP 80/443 abertas.
- Docker Compose v2, Caddy ou Nginx no mesmo host, com certificado TLS válido.
- Segredos fortes no .env privado (nunca em commit); cópia de segurança inicial.
- Firewall não deve publicar MySQL, nem a porta 8080 da aplicação. compose.yaml já fixa a porta HTTP em 127.0.0.1.

## Exemplo com Caddy no host

Substitua o domínio de exemplo e instale Caddy seguindo a documentação da distribuição.

    convites.example.com {
        encode gzip
        header Strict-Transport-Security "max-age=31536000"
        reverse_proxy 127.0.0.1:8080
    }

O proxy deve negociar TLS válido e renovar certificados. Não desabilitar validação de certificados, não encaminhar tráfego não autenticado às APIs administrativas de outra origem e não expor o serviço diretamente.

No .env privado, configure:

    APP_PUBLIC_URL=https://convites.example.com
    TRUSTED_PROXY_HOPS=0

Inicie os serviços do Compose após preencher senhas, hash do organizador e segredos. O valor padrão TRUSTED_PROXY_HOPS=0 ignora cabeçalhos X-Forwarded-For enviados por visitantes, sendo a opção conservadora até comprovar a topologia do proxy. Caso seja necessário ativar 1, o proxy deve **substituir** X-Forwarded-For por IP previamente validado, e a aplicação deve permanecer acessível apenas pelo loopback.

**Importante:** o limitador em memória da aplicação não controla taxas globais entre processos Gunicorn. Dimensionar proteção por IP no proxy/WAF e evitar bloquear todos os convidados por causa de uma única origem.

## Verificação não destrutiva da publicação

Após a implantação HTTPS, no computador de administração execute:

    python scripts/check_production.py --url https://convites.example.com

O comando não cria nem modifica convites. Verifica certificado TLS via biblioteca do sistema, health check, conteúdo da API pública, painel privado inacessível sem login, política CSP, não-cache, X-Frame-Options, HSTS e atributos reais do cookie de sessão (Secure, HttpOnly, SameSite=Lax e Path=/). A verificação usa parser de cookies para evitar falsos positivos quando essas palavras aparecem apenas no nome ou valor. HSTS deve ser emitido pelo proxy.

Se a verificação falhar, manter o acesso restrito e corrigir. Aprovação desse script é necessária, mas **não substitui** auditoria, teste de carga, restauração ou ensaio manual de dispositivos.

## Liberação definitiva pendente

1. Homologar domínio, DNS, HTTPS e proxy no servidor real.
2. Registrar backup criptografado externo, retenção e restauração no ambiente final.
3. Avaliar segredos, acesso administrativo, logs, disponibilidade e limitação distribuída de requisições.
4. Executar docs/manual-checklist.md em Android e iPhone reais, incluindo link do PDF aberto no WhatsApp.
5. Registrar revisão independente e aprovação explícita antes de compartilhar o endereço.
