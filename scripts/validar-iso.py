#!/usr/bin/env python3
"""Revalidação offline e somente leitura da base oficial; falha fecha o processo."""
import hashlib
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "xubuntu-24.04.5-minimal-amd64.iso"
FINGERPRINT = "843938DF228D22F7B3742BC0D94AA3F0EFE21092"


def expected_hash(text, name=NAME):
    matches = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[1].lstrip("*") == name:
            if not re.fullmatch(r"[0-9a-f]{64}", fields[0]):
                raise ValueError("SHA-256 inválido")
            matches.append(fields[0])
    if len(matches) != 1:
        raise ValueError("Entrada ausente ou duplicada no SHA256SUMS")
    return matches[0]


def valid_signature(status):
    fingerprints = [line.split()[2] for line in status.splitlines()
                    if line.startswith("[GNUPG:] VALIDSIG ")]
    return fingerprints == [FINGERPRINT]


def verify_digest(path, expected):
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != expected:
        raise ValueError("SHA-256 divergente; interromper")
    return actual


def main():
    source = ROOT / "sources"
    result = subprocess.run([
        "gpgv", "--homedir", str(source / "verification"),
        "--keyring", str(source / "verification/trustedkeys.gpg"),
        "--status-fd", "1", str(source / "SHA256SUMS.gpg"),
        str(source / "SHA256SUMS")], capture_output=True, text=True)
    if result.returncode or not valid_signature(result.stdout):
        raise ValueError("Assinatura inválida ou signatário inesperado; interromper")
    expected = expected_hash((source / "SHA256SUMS").read_text())
    digest = verify_digest(source / NAME, expected)
    print("GPG: OK; fingerprint:", FINGERPRINT)
    print("SHA-256: OK;", digest)
    print("ISO bytes:", (source / NAME).stat().st_size)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        raise SystemExit(str(error))
