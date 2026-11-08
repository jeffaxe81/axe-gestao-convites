# Isadora — critério para concluir a liberação em 100%

**Data de referência:** 08/11/2026. **Evento:** 13/12/2026, às 15h (Brasília).

## Estado comprovado

- O núcleo do gerenciador foi integrado à `main` na PR #1.
- A execução **42478818971** passou em **230 testes**, Docker Compose, persistência e backup cifrado com restauração das quatro tabelas.
- O ZIP do código-fonte versionado é disponibilizado como artefato da CI.
- O domínio pode ser definido depois, sem mudar o código-fonte.

Esses resultados comprovam desenvolvimento/ambiente descartável. A liberação de convidados continua em **86% (6/7 etapas)** até o encerramento real da etapa 7.

## Verificações indispensáveis para a etapa 7

| ID | Verificação | Evidência necessária | Situação inicial |
|---|---|---|---|
| dns_https | DNS, TLS, cabeçalhos e autenticação em HTTPS público | URL real testada de rede externa com `check_production.py`; registrar resultado fora do repositório | Pendente |
| backup_externo | Backup cifrado e restauração em host definitivo, sem sobrescrever produção | Log de recuperação isolada, comparação das quatro tabelas, cofre/retensão externa | Pendente |
| android_real | Receber PDF no WhatsApp de Android físico, confirmar/recusar/editar | Registro privado de modelo, versão, horário e resultado, sem nomes ou tokens | Pendente |
| iphone_real | Mesmo fluxo em iPhone físico e Safari | Registro privado de modelo, versão, horário e resultado | Pendente |
| revisao_seguranca | Revisão independente dos controles e do proxy | Referência ao parecer, pendências corrigidas, responsável | Pendente |
| aceite_operacional | Aprovação final para envio | Documento com decisão do organizador e responsável técnico | Pendente |

## Coleta sem dados pessoais

Copie `docs/release-evidence-template.json` **para uma pasta privada fora do Git**. Mantenha os valores `verified=false` até a execução real. Quando um teste for concluído, indique `verified=true`, data ISO 8601 com fuso em `verified_at`, e um identificador **não sensível** de evidência em `evidence_ref` (por exemplo, `QA-ANDROID-20261108-001`).

Não use nomes de convidados, URLs de edição, credenciais, backups nem relatórios nominais nesse arquivo. A evidência propriamente dita deve permanecer no armazenamento privado autorizado.

Exemplo seguro de arquivo com os seis itens ainda pendentes:

```bash
python scripts/release_readiness.py --evidence-file docs/release-evidence-template.json
# Retorno 1: liberação bloqueada, enquanto houver itens pendentes.
```

O verificador exige os seis registros para considerar **completo o formulário de evidências** e sempre exige revisão humana posterior. Ele não confere sozinho a autenticidade de comprovantes, Android, iPhone ou HTTPS. Preencher `verified=true` sem executar testes é inválido como prova operacional.

## Procedimento recomendado

1. Preparar um servidor com Docker e banco persistente; criar `.env` privado e senhas fortes.
2. Rodar `python scripts/preflight.py --env-file .env`. O ambiente **local** pode ser validado com `--local`, mas não é publicação.
3. Configurar domínio e proxy TLS; verificar a URL com `python scripts/check_production.py --url https://DOMINIO_PUBLICO`.
4. Executar backup cifrado para armazenamento externo, restaurar em base temporária no host final e comparar quatro tabelas.
5. Produzir o PDF final somente depois de HTTPS aprovado, com `scripts/generate_invitation.py --check-production`.
6. Homologar o fluxo PDF/WhatsApp/RSVP/edição em Android e iPhone reais.
7. Concluir revisão de segurança e obter aceite operacional explícito.
8. Atualizar a evidência privada, conferir manualmente e **somente então** distribuir convites.

## Não fabricar 100%

Não são válidas como substitutas: screenshot de navegador emulado, testes no runner, DNS provisório, `http://localhost`, backup sem restauração externa ou declaração automática de aceite.

O relatório de progresso da Release 1 permanecerá em **86%** enquanto qualquer uma das condições acima for desconhecida ou não validada.
