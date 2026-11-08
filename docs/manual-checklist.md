## Pré-homologação local sem domínio (somente leitura)
- [ ] Iniciar Docker Compose em uma máquina de teste; configurar senhas privadas exclusivas e `APP_PUBLIC_URL` local.
- [ ] Executar `python scripts/preflight.py --env-file .env --local` e documentar resultado sem publicar segredos.
- [ ] Executar `python scripts/check_local.py --json`; registrar PASS nas oito verificações HTTP.
- [ ] Conferir que o smoke test não criou RSVP fictício: são somente requisições GET, sem login de administrador.
- [ ] Confirmar que respostas atrasadas durante logout não voltam a exibir nomes ou contadores.
- [ ] Separadamente, realizar os testes funcionais de gravação usando convidados fictícios em ambiente descartável.

# Checklist manual — Isadora Release 1

Todas as caixas abaixo permanecem desmarcadas até testes reais. Registrar data, dispositivo/versão, responsável, passos e evidência sem publicar nomes de convidados.

## Preparação do PDF
- [ ] Gerar PDF final apenas após validação da origem HTTPS real.
- [ ] Validar QR Code e botão do PDF; não encaminhar a demonstração.
- [ ] Testar PDF em leitor e WhatsApp de aparelhos reais; conferir que não expõe link de edição privada.

## Android — abertura do convite via WhatsApp
- [ ] Receber PDF do convite no WhatsApp e abrir o link de confirmação.
- [ ] Conferir legibilidade, contraste, foco, teclado, toque e ausência de rolagem horizontal.
- [ ] Enviar confirmação com um adulto e crianças de 5, 6 e 12 anos.
- [ ] Enviar recusa com nome; conferir agradecimento.
- [ ] Guardar link privado e editar a própria confirmação, sem criar duplicidade.
- [ ] Simular perda de rede e reenvio; verificar que não duplica e não exibe sucesso falso.

## iPhone — abertura do convite via WhatsApp/Safari
- [ ] Repetir fluxo de PDF para página de confirmação.
- [ ] Conferir responsividade, teclado, seleção de faixa etária e datas.
- [ ] Confirmar, recusar, revisar e editar pelo link privado.
- [ ] Verificar comportamento após prazo de edição.
- [ ] Conferir campos obrigatórios, mensagens de erro e agradecimento.

## Área dos organizadores
- [ ] Login/logout em HTTPS, sem exibir contagens para quem não está autenticado.
- [ ] Conferir totais com famílias conhecidas: buffet, 0–5, 0–12, acima de 12, recusas.
- [ ] Conferir nomes para lembrancinhas e alterações dos participantes.
- [ ] Alterar local sem mudar URL da página; atualizar e remover prazo de edição.
- [ ] Verificar alertas quando buffet atingir e ultrapassar 40, sem bloquear convidado.

## Operação e liberação
- [ ] Confirmar DNS, certificado TLS, reverse proxy e cookies Secure em produção.
- [ ] Se ativar TRUSTED_PROXY_HOPS=1, conferir que a aplicação não é exposta diretamente e o proxy substitui X-Forwarded-For (nunca repassa valor arbitrário do cliente).
- [ ] Conferir limites distribuídos no proxy/WAF, porque o rate limit do Flask é apenas por processo.
- [ ] Configurar autenticação/segredos fortes sem arquivos sensíveis versionados.
- [ ] Configurar backups, testar restauração e definir retenção/eliminação de dados pessoais.
- [ ] Registrar aprovador técnico antes de compartilhar o convite.

## Funcionalidades de novembro — validação real

- [ ] Conferir que histórico de movimentos mostra apenas tipo e horário, sem nome, IP ou token.
- [ ] Verificar se as movimentações de criação, recusa, edição e configuração aparecem uma única vez após salvar.
- [ ] Exportar resumo buffet/lembrancinhas sem dados identificáveis e conferir com a contagem oficial.
- [ ] Imprimir a lista pelo navegador, tanto completa quanto filtrada, e confirmar que campos privados de configuração ficam ocultos.
- [ ] Executar migração aditiva no banco de homologação com convites pré-existentes, confirmando preservação.
- [ ] Fazer backup cifrado e restaurar em instância isolada com quatro tabelas, inclusive histórico.

## Rodada de 20 melhorias — verificação em dispositivos reais

- [ ] Testar link .ics em agenda Android e iPhone: horário de 15h em 13/12/2026, local atualizado.
- [ ] Conferir data/horário e contagem regressiva no fuso de Brasília.
- [ ] Desligar dados móveis/Wi-Fi durante uma confirmação; verificar aviso e ausência de sucesso falso.
- [ ] Reativar a rede e reenviar; confirmar que há apenas um RSVP, sem duplicação.
- [ ] Validar contador e limite de participantes, foco de erro em nome/idade, etapas e Escape com teclado externo.
- [ ] Testar leitor de tela e modo contraste alto/redução de movimentos.
- [ ] Verificar o arquivo CSV do buffet com a faixa de 6 a 12 anos e três novos indicadores do painel.
- [ ] Verificar que o link privado é copiado corretamente sem expô-lo em mensagens ou logs.

## Rede instável e WebKit — homologação física complementar

- [ ] Em Android físico, interromper internet durante envio e confirmar que o botão volta a funcionar sem resposta falsa.
- [ ] Repetir o envio com a mesma resposta após conexão instável; conferir uma única confirmação no painel.
- [ ] Em iPhone físico, repetir envio, edição e retentativa no Safari, inclusive pelo PDF recebido no WhatsApp.
- [ ] Confirmar que a mensagem de espera de 15 segundos é compreensível e não indica que o banco certamente não gravou.
