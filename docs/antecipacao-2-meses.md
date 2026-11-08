# Isadora — antecipação técnica de dois meses

**Registro:** 08/11/2026. **Evento:** 13/12/2026, 15h, horário de Brasília.

Este plano concentra oito frentes equivalentes a semanas de evolução. **Não** afirma que oito semanas de operação ou homologação já ocorreram. Todas as evidências devem vir de código, CI ou testes reais devidamente registrados.

## Frentes de trabalho

| Frente | Escopo antecipado | Situação |
|---|---|---|
| 1. Administração | Histórico de confirmações, recusas, edições e alterações da festa | Código implementado, CI a verificar |
| 2. Privacidade | Histórico sem nome, telefone, ID familiar, link de edição ou token | Código e testes adicionados |
| 3. Planejamento buffet | CSV com quantidades sem identificação dos convidados | Código e testes adicionados |
| 4. Operação do evento | Impressão local de lista com filtro atual, formato A4 | Código e E2E adicionados |
| 5. Consistência | Registro de atividade na mesma transação de cada alteração | Código e regressão adicionados |
| 6. Evolução de dados | Migração aditiva 002; preservação do banco existente | Código e teste adicionado |
| 7. Recuperação | Backup e validação de restauração incluem tabela de histórico | Código e CI devem confirmar |
| 8. Homologação | Testes Android/iPhone físicos, HTTPS, DNS, backup externo e aceite | Pendente de ambiente real |

## Fluxos implementados

- O histórico fica disponível apenas após autenticação em **Organizar > Consultar histórico**. Lista até 50 movimentos recentes, sem PII. A visualização é limpa ao sair ou expirar sessão.
- O botão **Resumo buffet/lembrancinhas** baixa um CSV específico para fornecedores e família. Contém somente totais: participantes, buffet, crianças e limite, sem nomes.
- O botão **Imprimir lista** abre a impressão nativa do navegador; considera a pesquisa atualmente aplicada às listas. O CSS oculta configurações, formulário de login e controles, mantendo listas e contadores.
- As tabelas de confirmação e eventos permanecem sob transação única. Retentativas idempotentes, edição sem sucesso ou salvamento de configuração sem alteração não criam movimentação extra.
- A migração preserva respostas antigas e adiciona a tabela de histórico. A ferramenta de backup compara quatro tabelas após restauração, incluindo o histórico.

## Regras de segurança e privacidade

O histórico não substitui auditoria de segurança independente: é uma trilha mínima de ações (tipo e data/hora). Não há trilha nominal de autores, IPs ou convidados. Nunca colocar nome de criança ou token privado em issue, commits ou logs. O resumo CSV não identifica famílias, mas ainda deve ser verificado antes de compartilhar.

O relatório completo e a impressão local podem incluir nomes de pessoas. São recursos restritos ao organizador; proteger arquivos gerados e documentos impressos. O sistema não envia automaticamente mensagens de WhatsApp.

## Marco de conclusão

A Release 1 permanece em **86% (6/7 etapas)** até completar a fase 7 de homologação real. O aceite depende de domínio seguro, revisão final, backup externo restaurável, demonstração/convite testado pelo WhatsApp nos aparelhos físicos e autorização do responsável.

**Repositório:** https://github.com/jeffaxe81/axe-gestao-convites

**PR:** https://github.com/jeffaxe81/axe-gestao-convites/pull/1

**CI:** consultar execução associada ao commit final na PR #1. Não declarar testes aprovados antes de aparecerem como concluídos com sucesso.

## Pós-evento (após 13/12/2026)

Definir uma política de retenção e descarte compatível com o contexto e a legislação aplicável. Não automatizar remoção destrutiva sem política aprovada, backup e aceite explícito. A existência de relatórios e de histórico não autoriza armazenamento permanente dos dados dos convidados.
