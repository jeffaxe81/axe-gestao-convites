# Isadora — antecipação de um mês (4 frentes executadas em 18/10/2026)

Este documento descreve entregas verificáveis, **não** equivale a afirmar que um mês de testes externos ou operação real aconteceu. O evento continua previsto para 13/12/2026.

## Semana 1: operação dos organizadores

- [x] Exportação CSV de confirmados, recusas, faixas etárias, buffet e lembrancinhas.
- [x] Download exclusivo do painel autenticado; resposta não armazenável em cache.
- [x] Proteção contra injeção de fórmula no Excel e arquivo UTF-8 para Windows.
- [x] Testes de API e teste de download em Chromium adicionados.
- [ ] Validar exportação na instalação real e conferir arquivos no Excel do organizador.

## Semana 2: segurança dos dados

- [x] Ferramenta de cifragem de backup com AES-256-GCM e scrypt.
- [x] Descriptografia rejeita alteração ou senha incorreta, sem preservar arquivo parcial.
- [x] Arquivos gerados com modo 0600 e sem sobrescrita.
- [x] CI inclui ida-e-volta criptográfica, comparação binária e restore MySQL isolado.
- [ ] Instalar armazenamento externo/retido e cofre de segredos em produção.

## Semana 3: implantação

- [x] Script preflight para detectar .env exposto, senhas triviais, placeholders e URL HTTP.
- [x] Verificação de política de proxy e hash de autenticação dos organizadores.
- [x] Script de inspeção HTTPS já incluído na etapa anterior.
- [ ] Configurar DNS, servidor, certificado HTTPS e proxy/WAF reais.

## Semana 4: qualidade e liberação

- [x] Testes de acesso não autenticado e logout para o relatório.
- [x] Testes de falha de autenticidade do backup e de não sobrescrita.
- [x] Testes de configuração operacional.
- [ ] Ensaios em Android e iPhone físicos recebendo o link em PDF pelo WhatsApp.
- [ ] Auditoria independente, aprovação de privacidade e teste de restauração no host final.

## Critério de progresso

A Release 1 possui sete etapas principais e continua em **86% (6/7 concluídas)**. As quatro frentes antecipadas agregam código e testes à etapa 7; nenhuma etapa de ambiente real pode ser dada como concluída apenas por simulação/CI. A PR #1 continua aberta como rascunho e não deve ser mesclada à main antes da homologação.

GitHub: https://github.com/jeffaxe81/axe-gestao-convites/pull/1

Consulte docs/validation.md e as execuções do Actions para obter contagem atual de testes. Não enviar convites reais sem liberação expressa.
