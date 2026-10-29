#!/usr/bin/env python3
"""Backup MySQL do Isadora e prova de restauração em banco descartável.

O arquivo .sql.gz contém dados pessoais em texto legível depois de descompactado.
Proteja-o com criptografia e armazenamento externo; nunca publique no repositório.
"""
import argparse
import gzip
import hashlib
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys

COMPOSE = ["docker", "compose", "exec", "-T", "db", "sh", "-ec"]
ROOT_SQL = 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql --batch --raw --skip-column-names -uroot -e "$1"'
DUMP = (
    'MYSQL_PWD="$MYSQL_PASSWORD" exec mysqldump '
    '--single-transaction --quick --no-tablespaces --set-gtid-purged=OFF '
    '--default-character-set=utf8mb4 -u "$MYSQL_USER" "$MYSQL_DATABASE"'
)
DATA_COLUMNS = {
    "event_settings": "id, venue, edit_deadline_utc, buffet_limit",
    "families": (
        "id, contact_name, attending, revision, submission_key_hash, "
        "payload_hash, edit_token_hash"
    ),
    "participants": "id, family_id, position, name, kind, age_years",
}


def run_db(script, *args):
    proc = subprocess.run(
        COMPOSE + [script, "sh", *args],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if proc.returncode:
        raise RuntimeError(
            "Comando MySQL falhou (código {}). Confira Docker e permissões.".format(
                proc.returncode
            )
        )
    return proc.stdout


def database_name():
    name = run_db('printf "%s" "$MYSQL_DATABASE"').decode("utf-8").strip()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name):
        raise RuntimeError("Nome de banco inválido no contêiner.")
    return name


def backup(target):
    target = Path(target).expanduser()
    root = Path(__file__).resolve().parents[1]
    destination = target.parent.resolve() / target.name
    if destination == root or root in destination.parents:
        raise ValueError("Grave o backup fora do repositório para evitar vazamento.")
    if not target.name.endswith(".sql.gz"):
        raise ValueError("O arquivo de backup deve terminar em .sql.gz.")
    if not destination.parent.is_dir():
        raise ValueError("Diretório de destino inexistente.")
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as output:
            with gzip.GzipFile(fileobj=output, filename="", mode="wb", mtime=0) as gz:
                proc = subprocess.Popen(
                    COMPOSE + [DUMP],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                assert proc.stdout is not None
                assert proc.stderr is not None
                shutil.copyfileobj(proc.stdout, gz, length=128 * 1024)
                proc.stdout.close()
                errors = proc.stderr.read()
                code = proc.wait()
                if code:
                    raise RuntimeError(
                        "mysqldump falhou (código {}): {}".format(
                            code, errors.decode("utf-8", "replace")[:800]
                        )
                    )
        if destination.stat().st_size < 100:
            raise RuntimeError("Backup inesperadamente pequeno; verifique o banco.")
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    print("Backup gerado com acesso restrito (0600): {}".format(destination))
    print("ATENÇÃO: .sql.gz não é criptografado; cifre antes de armazenar/transferir.")


def query_digest(database, table, columns):
    query = "SELECT {} FROM {}.{} ORDER BY {};".format(
        columns, database, table, "id"
    )
    script = 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql --batch --raw --skip-column-names -uroot -e "$1"'
    proc = subprocess.Popen(
        COMPOSE + [script, "sh", query],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    assert proc.stdout is not None
    assert proc.stderr is not None
    digest = hashlib.sha256()
    total = 0
    while True:
        block = proc.stdout.read(128 * 1024)
        if not block:
            break
        digest.update(block)
        total += len(block)
    proc.stdout.close()
    errors = proc.stderr.read()
    code = proc.wait()
    if code:
        raise RuntimeError(
            "Comparação {}.{} falhou (código {}): {}".format(
                database, table, code, errors.decode("utf-8", "replace")[:800]
            )
        )
    return digest.hexdigest(), total


def validated_backup_source(source):
    source = Path(source).expanduser()
    if source.is_symlink() or not source.is_file() or not source.name.endswith(".sql.gz"):
        raise ValueError("Informe um backup .sql.gz regular, sem link simbólico.")
    if os.name == "posix" and source.stat().st_mode & 0o077:
        raise ValueError("Proteja o backup com chmod 600 antes de restaurar.")
    return source


def verify_restore(source):
    source = validated_backup_source(source)
    original = database_name()
    temporary = "isadora_restore_" + secrets.token_hex(6)
    baseline = {
        table: query_digest(original, table, columns)
        for table, columns in DATA_COLUMNS.items()
    }
    created = False
    try:
        run_db(ROOT_SQL, "CREATE DATABASE {} CHARACTER SET utf8mb4;".format(temporary))
        created = True
        script = 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -uroot "$1"'
        with gzip.open(source, "rb") as input_sql:
            proc = subprocess.Popen(
                COMPOSE + [script, "sh", temporary],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            assert proc.stdin is not None
            assert proc.stderr is not None
            try:
                shutil.copyfileobj(input_sql, proc.stdin, length=128 * 1024)
            finally:
                proc.stdin.close()
            errors = proc.stderr.read()
            code = proc.wait()
            if code:
                raise RuntimeError(
                    "Restauração falhou (código {}): {}".format(
                        code, errors.decode("utf-8", "replace")[:800]
                    )
                )
        restored = {
            table: query_digest(temporary, table, columns)
            for table, columns in DATA_COLUMNS.items()
        }
        if baseline != restored:
            raise RuntimeError(
                "Falha: dados atuais diferem do arquivo restaurado. "
                "Não houve alteração no banco original."
            )
        print("PASS: restore temporário validado; três tabelas idênticas ao original.")
    finally:
        if created:
            run_db(ROOT_SQL, "DROP DATABASE {};".format(temporary))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_subparsers(dest="action", required=True)
    action.add_parser("backup").add_argument("--output", required=True)
    action.add_parser("verify-restore").add_argument("--input", required=True)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        if args.action == "backup":
            backup(args.output)
        else:
            verify_restore(args.input)
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print("ERRO: {}".format(exc), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
