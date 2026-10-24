# Backup e restauração — Isadora Release 1

**Estado:** ferramenta de backup e prova de restauração em base descartável implementadas. Homologação na hospedagem final e procedimento real de desastre permanecem pendentes.

## Pré-requisitos

- Docker Compose v2 e contêiner MySQL 8.4 em execução.
- Executar no diretório do projeto, com arquivo .env privado.
- Pasta de backup fora do repositório, acessível apenas ao operador.
- Espaço livre para um arquivo SQL comprimido. **O dump não é criptografado** pela ferramenta.

## Criar backup

    mkdir -p "$HOME/isadora-backups" && chmod 700 "$HOME/isadora-backups"
    python scripts/backup_mysql.py backup --output "$HOME/isadora-backups/isadora-2026-10-18.sql.gz"

O utilitário executa mysqldump --single-transaction --quick no contêiner, compacta o resultado e cria arquivo com permissão 0600 sem sobrescrever outro existente. O banco original não é alterado. Use nome diferente no backup seguinte.

**Obrigatório:** criptografar o arquivo antes de transferir a armazenamento externo, aplicar controle de acesso, definir retenção, proteger os segredos da aplicação e manter cópia em local distinto do servidor. Não anexar dumps a issues, PRs, chats públicos, artefatos públicos de CI ou mensagens dos convidados.

## Validar restauração sem destruir dados

Em uma janela sem novas respostas ou alterações dos convidados, executar:

    python scripts/backup_mysql.py verify-restore --input "$HOME/isadora-backups/isadora-2026-10-18.sql.gz"

O comando cria um banco temporário de nome aleatório começando por isadora_restore_, importa o dump e compara integralmente os dados ordenados de event_settings, families e participants com o banco de origem. O banco temporário é excluído ao final. **Não sobrescreve nem descarta a base original.**

Se os convidados enviarem ou alterarem respostas depois do backup, a comparação com a base atual poderá falhar mesmo que o dump esteja íntegro. Para uma prova consistente, suspender gravações entre a geração do arquivo e a verificação.

## Recuperação após incidente real

A ferramenta não faz recuperação destrutiva da base principal. O restore real deve ser feito por operador autorizado em uma instância separada, após autorização e cópia do estado atual.

1. Suspender gravações e isolar o banco afetado.
2. Confirmar backup, chave de criptografia e compatibilidade de versão.
3. Preparar MySQL compatível separado e importar a cópia.
4. Conferir famílias, participantes, configurações e links de edição.
5. Executar o smoke test da aplicação na nova instância.
6. Registrar aprovação, janela de recuperação e rollback antes de alterar o tráfego.

**Não executar DROP, TRUNCATE ou exclusão de volume de produção** com base nestas instruções resumidas.

## Critérios ainda pendentes para produção

- Frequência, retenção e expurgo.
- Criptografia, armazenamento externo e recuperação de chaves.
- Monitoramento de execução, espaço livre e falhas.
- Ensaio de desastre na infraestrutura final, com RPO e RTO definidos.
- Política de descarte de dados pessoais após o evento.

## Criptografia autenticada — novidade

O script `scripts/secure_backup.py` usa **AES-256-GCM**, nonce aleatório, salt aleatório e chave derivada com scrypt. A criptografia é em fluxo, sem precisar manter o dump completo em memória. O arquivo resultante tem extensão `.isadora`. Qualquer alteração no arquivo cifrado ou senha incorreta faz a recuperação falhar.

Instalar a dependência na máquina de operação:

```bash
python -m pip install -r requirements-ops.txt
```

Para cifrar o backup, execute os comandos em um terminal privado. O programa pede a frase secreta sem mostrá-la na linha de comando, caso `ISADORA_BACKUP_PASSPHRASE` não esteja definido:

```bash
python scripts/secure_backup.py encrypt --input "$HOME/isadora-backups/isadora-2026-10-18.sql.gz" --output "$HOME/isadora-backups/isadora-2026-10-18.sql.gz.isadora"
```

Para recuperar o backup **em um diretório privado**:

```bash
python scripts/secure_backup.py decrypt --input "$HOME/isadora-backups/isadora-2026-10-18.sql.gz.isadora" --output "$HOME/isadora-backups/restaurado.sql.gz"
python scripts/backup_mysql.py verify-restore --input "$HOME/isadora-backups/restaurado.sql.gz"
```

A ferramenta não exclui automaticamente o backup original sem criptografia, pois a exclusão deve ocorrer **somente depois** de conferir a recuperação e a retenção necessárias. Apague com segurança cópias temporárias conforme as políticas do servidor. Armazene a chave/frase secreta em gerenciador externo, separado dos arquivos. **Perder a frase secreta impede recuperar o backup cifrado.**

Os testes automatizados de ida-e-volta da cifra e a prova MySQL estão na CI. **Ainda é obrigatório** testar o procedimento em hospedagem real e assegurar backup externo seguro.

Para execução automatizada sem terminal, a variável `ISADORA_BACKUP_PASSPHRASE` é suportada, mas deve vir de um cofre de segredos; não incluí-la em logs, histórico de shell, `.env` versionado ou comandos compartilhados.
