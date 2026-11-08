# Isadora — 20 entregas de melhorias

**Rodada:** 08/11/2026. **Escopo:** convite da Isadora, Release 1.
**Status de liberação:** continua em 86% (seis de sete etapas). Não distribuir convite real antes da homologação.

## As 20 entregas

| Nº | Melhoria | Evidência técnica / critério |
|---:|---|---|
| 1 | Arquivo de calendário para a festa (.ics) | GET /evento.ics, UTC, nome e local públicos, sem dados de RSVP |
| 2 | Botão público para adicionar a data ao calendário | Link acessível no cabeçalho do convite |
| 3 | Data e horário sincronizados com a API | Fuso America/Sao_Paulo; não depender só do texto estático |
| 4 | Contagem regressiva para a festa | Mensagem de dias restantes, oculta quando data inválida |
| 5 | Aviso visual de ausência de conexão | Área aria-live, aviso apresentado quando navegador está offline |
| 6 | Bloqueio seguro de envio offline | Sem confirmação falsa e sem apagar resposta digitada |
| 7 | Recuperação visual ao reconectar | Aviso é retirado; usuário pode reenviar conscientemente |
| 8 | Contador automático de participantes | Atualiza ao incluir/remover acompanhante |
| 9 | Limite de 100 participantes na interface | Botão desabilitado ao atingir limite, habilitado após remoção |
| 10 | Foco automático no nome principal inválido | Conduz diretamente ao campo que precisa ser preenchido |
| 11 | Foco automático no acompanhante inválido | Conduz ao campo vazio do acompanhante |
| 12 | Foco automático na idade inválida | Número inteiro de 0–12 anos, com foco no campo correto |
| 13 | Indicador de etapas 1/3, 2/3 e 3/3 | Resposta, revisão e confirmação registrados visualmente |
| 14 | Voltar da revisão por Escape e com foco recuperado | Navegação por teclado e botão Voltar |
| 15 | Indicador de carregamento ao editar RSVP | Estado de busca mostrado até fim do carregamento |
| 16 | Mensagens acessíveis para copiar o link privado | Confirmação da cópia ou alternativa para copiar manualmente |
| 17 | Respeito à preferência de movimento reduzido | CSS com prefers-reduced-motion |
| 18 | Melhor suporte a contraste forçado | CSS para escolhas selecionadas e elementos de foco |
| 19 | Proteção de indexação e contexto do navegador | robots.txt + X-Robots-Tag + Cross-Origin-Opener-Policy |
| 20 | Três indicadores administrativos e CSV por idade | Famílias sim/não, crianças 6–12, relatório sem nomes |

## Alterações existentes preservadas

- RSVP com confirmação e recusa, revisão, idempotência e link privado de edição.
- Regras: crianças de 0 a 5 não entram na contagem do buffet; 6 a 12 entram no buffet e nas lembrancinhas; acima de 12 entram no buffet.
- Alerta de 40 lugares no buffet, sem bloquear confirmações.
- Painel autenticado, exportação nominal, CSV agregado, histórico sem nomes/tokens, backup cifrado e teste de restauração.
- Gerador offline do convite PDF com link e QR Code; sem envio automático de mensagens.
- Porta MySQL não publicada, HTTPS obrigatório para endereço externo, política de backup e dados pessoais.

## Testes adicionados

- Contratos do calendário ICS, fuso UTC, local com caracteres especiais e tentativa de injeção de nova propriedade.
- Diretivas robots e cabeçalhos de segurança nas rotas públicas.
- Contador e limite de participantes, foco em campos inválidos, etapas, Escape e retorno à edição.
- Rede offline, ausência de sucesso falso, reconexão e envio manual.
- Acessibilidade do texto de cópia do link.
- Contadores adicionais do organizador e limpeza da sessão na saída.
- Agrupamento 6–12 no CSV quantitativo, sem nomes.

Os testes também precisam passar junto com toda a suíte preexistente no GitHub Actions. As validações automáticas não substituem Android/iPhone físicos, DNS, TLS, armazenamento externo e recuperação na hospedagem real.

## Liberação e percentual

O desenvolvimento está na branch **feat/isadora-release-1**, PR #1. Aguardam liberação definitiva: domínio/HTTPS, backup externo validado em servidor real, testes reais de PDF recebido no WhatsApp em Android/iPhone, revisão independente e aceite operacional. O progresso permanece **86%** até essas etapas serem aprovadas.

https://github.com/jeffaxe81/axe-gestao-convites/pull/1
