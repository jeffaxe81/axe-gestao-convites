# Isadora — homologação de 1.000.000.000 de operações simuladas

**Registro:** 08/11/2026. **Objetivo:** envio, reenvio e controle de convidados com volume alto, sem atingir servidor real ou dados de famílias verdadeiras.

## Camadas de teste

### 1. Um bilhão de operações de MODELO, não um bilhão de HTTP

- Código-fonte: `tests/stress/rsvp_billion.c`, compilado em C11 com otimização e avisos estritos.
- Execução: `cc -std=c11 -O3 -Wall -Wextra -Werror tests/stress/rsvp_billion.c -o /tmp/isadora-billion && /tmp/isadora-billion 1000000000`.
- A mesma execução é disparada na CI, com timeout de 120 segundos, **após os testes reais de aplicação**.
- Opera exclusivamente sobre até 4.096 famílias sintéticas em memória, sem criar registros MySQL ou enviar chamadas para URLs.
- Um gerador pseudorrandômico determinístico executa criação, reenvios com mesma chave, conflitos por mesma chave com dados diferentes, edições otimistas válidas, revisões antigas rejeitadas, confirmações e recusas.
- Calcula totais incrementais de buffet e lembrancinhas; a cada 2.097.152 operações, recalcula todas as famílias de forma independente para detectar qualquer divergência.
- Invariantes: recusas não consomem buffet nem lembrancinhas, nenhuma família confirmada tem zero participantes, 0–5 não entra no buffet, 6–12 entra no buffet e recebe lembrancinha, acima de 12 entra no buffet. Idempotência e edição antiga não podem alterar contagens. Totais agregados precisam corresponder ao recálculo.

**Resultado no teste local inicial:** `PASS simulated_state_operations=1000000000`. A execução local concluiu sem falha de invariantes. Resultado oficial da CI associado à PR deve ser consultado antes de declarar o incremento homologado.

### 2. Integração Flask real com banco descartável

- `tests/integration/test_rsvp_load_matrix.py` envia dados fictícios a rotas HTTP de Flask em ambiente de teste, com persistência SQLAlchemy/SQLite isolada.
- 160 criações, 160 repetições idempotentes, 15 reutilizações conflitantes de chave, 54 atualizações de participação e 54 reedições obsoletas: **443 tentativas reais de gravação na API de teste**, além de leituras autenticadas/não autenticadas.
- As categorias de idade variam entre 0, 5, 6, 12 e acima de 12. Verifica respostas HTTP, revisão, idempotência, privacidade, número de famílias, históricos e comparação independente de totais.
- A CI continua verificando separadamente MySQL 8.4, persistência de volumes e restauração.

### 3. Navegador e rede

- Testes em Chromium e WebKit simulam fluxos equivalentes aos navegadores Android/Safari, edição pelo token privado, perda de rede e reconexão.
- Um teste simula POST pendente por 15 segundos, exige recuperação do botão sem falso sucesso e reenfileiramento consciente com a mesma chave.
- Não enviar um bilhão de requisições a um serviço real: isso poderia causar indisponibilidade e não é uma prática apropriada de homologação.

## Como interpretar os resultados

`1.000.000.000` representa **operações do modelo de estados e políticas de contagem**, não bilhões de execuções do backend Flask, transações MySQL ou envios de convite por WhatsApp. O modelo valida invariantes sob sequência longa e múltiplas transições. Os testes Python/API e MySQL são camadas independentes que ligam essas regras ao sistema real.

A homologação de produção continua pendente dos controles em `docs/fechamento-100.md`: domínio HTTPS real, backup externo restaurado, Android e iPhone físicos, revisão de segurança e aceite. Não divulgar convites públicos apenas porque a simulação terminou.
