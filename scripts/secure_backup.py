#!/usr/bin/env python3
"""Cifra backups da Isadora com AES-256-GCM; nunca grava senhas no repositório.

Formato v1: magic 8 bytes | salt 16 | nonce 12 | ciphertext | tag 16.
Apenas dados pessoais de backup; os segredos da aplicação exigem gestão separada.
"""
import argparse
from getpass import getpass
import os
from pathlib import Path
import secrets
import sys

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC = b"ISADORA1"
SALT_SIZE = 16
NONCE_SIZE = 12
TAG_SIZE = 16
BLOCK_SIZE = 256 * 1024


def _derive(passphrase, salt):
    if len(passphrase) < 16:
        raise ValueError("Frase secreta deve conter pelo menos 16 caracteres.")
    kdf = Scrypt(salt=salt, length=32, n=2**15, r=8, p=1)
    return kdf.derive(passphrase.encode("utf-8"))


def _paths(source, target, extension):
    source = Path(source).expanduser()
    dest = Path(target).expanduser()
    repository = Path(__file__).resolve().parents[1]
    full_dest = dest.parent.resolve() / dest.name
    if not source.is_file() or source.is_symlink():
        raise ValueError("Arquivo de entrada regular não encontrado.")
    if full_dest == repository or repository in full_dest.parents:
        raise ValueError("Salve arquivos de backup fora do repositório.")
    if not dest.name.endswith(extension):
        raise ValueError("Arquivo de saída exige extensão {}.".format(extension))
    if not full_dest.parent.is_dir():
        raise ValueError("Pasta de destino inexistente.")
    if source.resolve() == full_dest:
        raise ValueError("Entrada e saída devem ser arquivos diferentes.")
    return source, full_dest


def _output(dest):
    # O_EXCL evita sobrescrever backups e impede ataques via links simbólicos.
    fd = os.open(dest, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    return os.fdopen(fd, "wb")


def encrypt(source, target, passphrase):
    source, target = _paths(source, target, ".isadora")
    salt, nonce = secrets.token_bytes(SALT_SIZE), secrets.token_bytes(NONCE_SIZE)
    header = MAGIC + salt + nonce
    key = _derive(passphrase, salt)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(header)
    created = False
    try:
        with _output(target) as encrypted:
            created = True
            with source.open("rb") as plain:
                encrypted.write(header)
                while block := plain.read(BLOCK_SIZE):
                    encrypted.write(encryptor.update(block))
                encrypted.write(encryptor.finalize())
                encrypted.write(encryptor.tag)
    except BaseException:
        if created:
            target.unlink(missing_ok=True)
        raise
    print("PASS: arquivo cifrado com AES-256-GCM:", target)


def decrypt(source, target, passphrase):
    source, target = _paths(source, target, ".sql.gz")
    if not source.name.endswith(".isadora"):
        raise ValueError("Entrada deve terminar em .isadora.")
    length = source.stat().st_size
    header_len = len(MAGIC) + SALT_SIZE + NONCE_SIZE
    if length < header_len + TAG_SIZE:
        raise ValueError("Arquivo cifrado incompleto.")
    with source.open("rb") as encrypted:
        header = encrypted.read(header_len)
        if not header.startswith(MAGIC):
            raise ValueError("Formato de backup cifrado inválido.")
        salt = header[len(MAGIC):len(MAGIC) + SALT_SIZE]
        nonce = header[-NONCE_SIZE:]
        encrypted.seek(length - TAG_SIZE)
        tag = encrypted.read(TAG_SIZE)
        key = _derive(passphrase, salt)
        decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
        decryptor.authenticate_additional_data(header)
        encrypted.seek(header_len)
        remaining = length - header_len - TAG_SIZE
        created = False
        try:
            with _output(target) as plain:
                created = True
                while remaining:
                    block = encrypted.read(min(BLOCK_SIZE, remaining))
                    if not block:
                        raise ValueError("Backup cifrado truncado.")
                    remaining -= len(block)
                    plain.write(decryptor.update(block))
                # A integridade é autenticada antes que o arquivo seja aceito.
                plain.write(decryptor.finalize())
        except BaseException:
            if created:
                target.unlink(missing_ok=True)
            raise
    print("PASS: arquivo autenticado e decifrado:", target)
    print("ATENÇÃO: o arquivo .sql.gz resultante contém dados pessoais não cifrados.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for operation in ("encrypt", "decrypt"):
        operation_parser = sub.add_parser(operation)
        operation_parser.add_argument("--input", required=True)
        operation_parser.add_argument("--output", required=True)
    options = parser.parse_args()
    os.umask(0o077)
    secret = os.getenv("ISADORA_BACKUP_PASSPHRASE") or (
        getpass("Frase secreta do backup: ") if sys.stdin.isatty() else ""
    )
    if not secret:
        parser.error("Defina ISADORA_BACKUP_PASSPHRASE ou use terminal interativo.")
    try:
        if options.action == "encrypt":
            encrypt(options.input, options.output, secret)
        else:
            decrypt(options.input, options.output, secret)
    except (ValueError, OSError, InvalidTag) as exc:
        detail = "senha incorreta, arquivo adulterado ou corrompido" if isinstance(
            exc, InvalidTag
        ) else str(exc)
        print("ERRO: {}".format(detail), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
