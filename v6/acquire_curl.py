"""Acquire pinned curl packages using the signed Ubuntu security index."""
import hashlib
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

LISTS = Path("/var/lib/apt/lists")
PREFIX = "security.ubuntu.com_ubuntu_dists_noble-security_"
KEYRING = "/usr/share/keyrings/ubuntu-archive-keyring.gpg"
VERSION = "8.5.0-2ubuntu10.16"
PACKAGES = ("curl", "libcurl4t64", "libcurl3t64-gnutls")
ORIGIN = "https://security.ubuntu.com/ubuntu/"


def verified_index():
    release = LISTS / (PREFIX + "InRelease")
    text = subprocess.check_output(
        ["/usr/bin/gpgv", "--keyring", KEYRING, "--output", "-", str(release)],
        text=True,
    )
    matches = re.findall(r"(?m)^ ([0-9a-f]{64}) +(\d+) main/binary-amd64/Packages$", text)
    index = (LISTS / (PREFIX + "main_binary-amd64_Packages")).read_bytes()
    if matches != [(hashlib.sha256(index).hexdigest(), str(len(index)))]:
        raise ValueError("Índice amd64 não corresponde ao InRelease assinado")
    if "Suite: noble-security\n" not in text:
        raise ValueError("Origem inesperada")
    return index.decode()


def selected_records(index):
    records = {}
    for stanza in index.split("\n\n"):
        fields = dict(line.split(": ", 1) for line in stanza.splitlines()
                      if line and not line[0].isspace() and ": " in line)
        name = fields.get("Package")
        if name in PACKAGES and fields.get("Version") == VERSION and fields.get("Architecture") == "amd64":
            if name in records:
                raise ValueError("Pacote duplicado no índice")
            filename = f"{name}_{VERSION}_amd64.deb"
            if fields["Filename"] != f"pool/main/c/curl/{filename}":
                raise ValueError("Caminho de pacote inesperado")
            records[name] = fields
    if records.keys() != set(PACKAGES):
        raise ValueError("Versão fixada ausente no índice assinado")
    return records


def acquire(destination):
    records = selected_records(verified_index())
    destination.mkdir(parents=True, exist_ok=True)
    for name, fields in records.items():
        size = int(fields["Size"])
        path = destination / Path(fields["Filename"]).name
        if path.is_symlink():
            raise ValueError("Destino simbólico inesperado")
        if path.exists():
            data = path.read_bytes()
        else:
            with urllib.request.urlopen(ORIGIN + fields["Filename"], timeout=30) as response:
                data = response.read(size + 1)
        digest = hashlib.sha256(data).hexdigest()
        if len(data) != size or digest != fields["SHA256"]:
            raise ValueError(f"Hash ou tamanho incorreto: {name}")
        if not path.exists():
            with path.open("xb") as output:
                output.write(data)
        print(f"{digest}  {path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Informe o diretório exclusivo do payload")
    acquire(Path(sys.argv[1]))
