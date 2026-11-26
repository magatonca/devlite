# Instalador local da candidata v7

A modalidade local é exclusiva de candidata de homologação pessoal. A autorização de construção e a aprovação de uso definitivo ou distribuição são independentes. A rota Store continua disponível com assertions e os controles anteriores.

## Seed e integridade

O seed clássico Live usa o formato seed16. Somente a entrada `devlite-installer` pode usar `unasserted: true` e `classic: true`. Ela usa o arquivo `devlite-installer.snap`, sem snap-id, channel ou revisão atribuída pelo projeto, com SHA-256 fixo `841d68db724a6b040ab8237101d1703b97b0544231074c0f2756da930da529cb`. O snapd atribui a revisão local. Os demais snaps continuam com suas assertions autênticas, incluindo core22 no Live e o Firefox oficial nos dois seeds. O instalador está ausente da Base. [Implementação de seed16 no snapd](https://github.com/canonical/snapd/blob/master/seed/seed16.go)

A exceção não fornece assinatura de editor para o Snap DevLite. O confinamento classic tem acesso amplo ao sistema, conforme a arquitetura original. O AppArmor continua ativo para o sistema e os snaps confinados. O launcher mantém a inibição do automount com falha fechada e a camada Live restringe o diretório do socket a root:sudo com modo 0750. [Confinamento Snap](https://snapcraft.io/docs/explanation/security/classic-confinement/)

Referências locais de staging:

- Base em `work/v7-firefox-base-bZIYOzz9/var/lib/snapd/seed`.
- Live em `work/v7-local-seed-KYb3277n/seed`.
- Snap original do build em `work/v7-snap-build-AqXlIQHu/output`. Seus manifests e logs continuam como evidência. O artefato foi inspecionado sem execução.

Relatório de licença: o lint do Snapcraft apontou ausência de `license` nos metadados. Antes de distribuição, verificar licenças, avisos e eventuais obrigações de código-fonte por componente, incluindo binários Flutter, bibliotecas, Subiquity, Curtin e Probert. Registrar os avisos do build e declarar uma expressão de licença somente depois da revisão. O uso pessoal homologável não equivale à liberação de distribuição.

## Provisionar o snapshot administrativo

Execute somente com autorização administrativa. Revise o bootstrap e a unidade separadamente do código empacotado, assim como o manifesto e o conteúdo do snapshot. Os hashes abaixo identificam a cópia revisada nesta etapa. Uma mudança no código exige novo snapshot e novo recibo.

Os comandos pressupõem que /etc/devlite-v7 e a unidade ainda estejam ausentes. Se existir provisionamento anterior, preserve-o para revisão antes de migrar. Use um único shell como magaton.

```bash
set -euo pipefail
cd /home/magaton/DevLite-OS
archive="$PWD/work/v7-admin-review-Rae774Fp/worker.tar"
worker_sha=a8e04081c4f2c50e021a94c38ba351fa2093f569e50f353ac3d0ffa8dd4a6206
bootstrap_sha=aef659e7fa30788c0553a944a0717f25b5e20214803e792f5c7e4edb38b4f85c
unit_sha=626d0794c0abb95b5c1457501f15565d4e8357edc0ccb9b7a9546f1ce158be8c
archive_sha=4065b38b08c482736510ac4e29c78dc20ec8a505a669a6decc02fa05d1eec51b
base="$PWD/work/v7-firefox-base-bZIYOzz9/var/lib/snapd/seed"
live="$PWD/work/v7-local-seed-KYb3277n/seed"
source_iso="$PWD/artifacts/devlite-v6-6_np5ota/devlite-os-1.0-v6-amd64.iso"

printf '%s  %s\n' "$bootstrap_sha" v7/admin_bootstrap.py \
                    "$unit_sha" v7/devlite-v7-pack.service \
                    "$archive_sha" "$archive" | sha256sum -c -
test "$(tar -xOf "$archive" manifest.json | sha256sum | cut -d' ' -f1)" = "$worker_sha"
tar -tf "$archive"
test "$(df -B1 --output=avail /etc | tail -n1)" -ge 42050859008
test "$(stat -c %d /etc)" = "$(stat -c %d .)"
/usr/bin/python3 -B -m v7.seed "$base"
/usr/bin/python3 -B -m v7.seed "$live" --installer devlite-installer --local
```

Após revisar os arquivos, provisione a árvore nova. O processo privilegiado recebe por stdin somente os bytes que o usuário comum consegue ler. O bootstrap confere o manifesto e a ISO antes de expor as cópias finais.

```bash
test ! -e /etc/systemd/system/devlite-v7-pack.service
test ! -L /etc/systemd/system/devlite-v7-pack.service
sudo mkdir -m 0755 /etc/devlite-v7 /etc/devlite-v7/worker

put_admin() {
    local src=$1 dest=$2 mode=$3
    sudo install -m "$mode" /dev/null "$dest"
    cat -- "$src" | sudo tee "$dest" >/dev/null
}
put_admin v7/admin_bootstrap.py /etc/devlite-v7/bootstrap.py 0444
put_admin v7/devlite-v7-pack.service /etc/systemd/system/devlite-v7-pack.service 0444
printf '%s  %s\n' "$bootstrap_sha" /etc/devlite-v7/bootstrap.py \
                    "$unit_sha" /etc/systemd/system/devlite-v7-pack.service | sha256sum -c -
cat -- "$archive" | sudo /usr/bin/python3 -ISB /etc/devlite-v7/bootstrap.py --stage "$worker_sha"
cat -- "$source_iso" | sudo /usr/bin/python3 -ISB /etc/devlite-v7/bootstrap.py --stage-source
```

## Provisionar seeds e recibo

```bash
copy_seed() {
    local src=$1 dest=$2 sub item name
    sudo mkdir -m 0755 "$dest" "$dest/assertions" "$dest/snaps"
    put_admin "$src/seed.yaml" "$dest/seed.yaml" 0644
    for sub in assertions snaps; do
        for item in "$src/$sub/"*; do
            name=${item##*/}
            [[ $name =~ ^[A-Za-z0-9_,.-]+$ && -f $item && ! -L $item ]]
            put_admin "$item" "$dest/$sub/$name" 0644
        done
    done
}
copy_seed "$base" /etc/devlite-v7/base-seed
copy_seed "$live" /etc/devlite-v7/live-seed
receipt=$(mktemp)
/usr/bin/python3 -B - "$worker_sha" > "$receipt" <<'RECEIPT'
import json
import sys
from v7.release_gate import LOCAL_ACK, LOCAL_CHECKS
from v7.seed import LOCAL_SHA256

print(json.dumps({
    "installer_mode": "local",
    "installer_sha256": LOCAL_SHA256,
    "authorization": LOCAL_ACK,
    "validated": dict.fromkeys(LOCAL_CHECKS, True),
    "worker_sha256": sys.argv[1],
}, indent=2))
RECEIPT
cat -- "$receipt"
```

Instale o recibo após revisão. Ele vincula a ABI, os testes automatizados e a revisão do worker ao fingerprint administrativo. A homologação real continua pendente. Para a rota Store, use seeds autenticados, modo store, snap-id, SHA-256 do Snap de Store e todos os controles de REQUIRED_CHECKS.

```bash
put_admin "$receipt" /etc/devlite-v7/release.json 0444
sudo systemctl daemon-reload
bash /home/magaton/DevLite-OS/v7/build-manual.sh --preflight
```

## Construção manual em duas etapas

Após pré-voo aprovado e autorização explícita, execute a unidade diretamente. Mantenha recibo, snapshot, ISO, seeds e unidade fixos durante a construção. O Python roda isolado com site e bytecode de projeto desabilitados. As bibliotecas do Ubuntu e os binários de sistema integram a fronteira de confiança.

```bash
sudo systemctl start devlite-v7-pack.service
journalctl -u devlite-v7-pack.service -n 30 --no-pager
```

Após sucesso, troque ID_DO_PACK pelos oito caracteres da linha Pack verificado. Monte como magaton, sem sudo.

```bash
bash /home/magaton/DevLite-OS/v7/build-manual.sh --assemble /var/lib/devlite-v7/pack-ID_DO_PACK
```

A unidade só expõe o pack depois da limpeza e da auditoria. A montagem confere o fingerprint aprovado e usa a mesma ISO v6 root-owned. O resultado é uma candidata de homologação.

## Homologação da candidata

- Iniciar a ISO primeiro em modo Live. Verificar BIOS e UEFI e comparar o SHA-256 da ISO com o relatório. Confirmar `snap wait system seed.loaded`, a presença do instalador local somente no Live, o Firefox oficial pt-BR e AppArmor ativo.
- Abrir o instalador pela sessão Live. Confirmar DevLite OS 1.0 nas telas operacionais, créditos, idioma, contraste e resolução baixa. Verificar resposta do Subiquity pelo socket e rejeição para usuário fora do grupo autorizado. Confirmar que o daemon reinicia e que a interface informa falhas de conexão.
- Verificar inibição de automount durante execução e liberação ao fechar ou cancelar. Testar falha do inibidor e encerramento por sinal. Qualquer armazenamento usado no teste deve ser descartável.
- Usar armazenamento descartável para instalação manual, guiada e automatizada com Curtin. Conferir primeiro boot, identidade, ausência do Snap instalador no sistema instalado e logs. Revisar casos de falha, recuperação e instalação offline.
- Conferir DevControl e Polkit, Adminer via Firefox com MariaDB local e rejeição de clientes remotos, criação, consultas, importação e exportação. Conferir VS Code sob demanda, LibreOffice, Whisker, terminal, Docker, Apache, PHP, Composer, Node.js, TypeScript, Git, Python, OpenVPN, SSH, serviços e recursos. Usar o checklist completo do checkpoint da v7.

## Retomada após falha de log no pack 4dtny274

O snapshot anterior já está provisionado. Preserve-o junto da ISO v6 administrativa, dos seeds, da unidade e do bootstrap. O novo manifesto altera somente pipeline/devlite/runtime.py dentro do snapshot. Execute o roteiro após autorização administrativa.

```bash
set -euo pipefail
cd /home/magaton/DevLite-OS
review="$PWD/work/v7-admin-review-plSiYBuZ"
archive="$review/worker.tar"
old=a8e04081c4f2c50e021a94c38ba351fa2093f569e50f353ac3d0ffa8dd4a6206
new=c28b1755957f831ff0a19b4162c840930f1a67950a784b72331181b3499eab1a

sha256sum -c "$review/SHA256SUMS"
test "$(tar -xOf "$archive" manifest.json | sha256sum | cut -d' ' -f1)" = "$new"
printf '%s  %s\n' \
  aef659e7fa30788c0553a944a0717f25b5e20214803e792f5c7e4edb38b4f85c /etc/devlite-v7/bootstrap.py \
  626d0794c0abb95b5c1457501f15565d4e8357edc0ccb9b7a9546f1ce158be8c /etc/systemd/system/devlite-v7-pack.service \
  | sha256sum -c -
case "$(systemctl show -p ActiveState --value devlite-v7-pack.service)" in
  inactive|failed) ;;
  *) exit 1 ;;
esac

# Conferir a auditoria privada antes de autorizar a nova tentativa.
sudo cat /var/lib/devlite-v7/pack-4dtny274/audit.json

draft=$(mktemp)
/usr/bin/python3 -ISB - "$old" "$new" > "$draft" <<'V7_RECEIPT'
import json
from pathlib import Path
import sys

receipt = json.loads(Path('/etc/devlite-v7/release.json').read_text())
if receipt['worker_sha256'] != sys.argv[1]:
    raise SystemExit('O recibo ativo diverge do snapshot anterior revisado.')
receipt['worker_sha256'] = sys.argv[2]
print(json.dumps(receipt, indent=2))
V7_RECEIPT
diff -u /etc/devlite-v7/release.json "$draft" || test "$?" -eq 1

cat -- "$archive" | sudo /usr/bin/python3 -ISB /etc/devlite-v7/bootstrap.py --stage "$new"
backup="/etc/devlite-v7/release.$old.json"
test ! -e "$backup" && test ! -L "$backup"
sudo cp --no-clobber -- /etc/devlite-v7/release.json "$backup"
cmp /etc/devlite-v7/release.json "$backup"
staged=$(sudo mktemp /etc/devlite-v7/.release-XXXXXXXX)
cat -- "$draft" | sudo tee "$staged" >/dev/null
sudo chmod 0444 -- "$staged"
sudo mv -T -- "$staged" /etc/devlite-v7/release.json
bash v7/build-manual.sh --preflight
```

Após pré-voo aprovado, auditoria sem erros de limpeza e autorização de construção, inicie a mesma unidade com sudo systemctl start devlite-v7-pack.service. Use o novo identificador publicado para a montagem desprivilegiada. O pack 4dtny274 permanece como evidência.

## Retomada após o erro do Apache no pack xx7nyohf

Reutilize integralmente o bloco de retomada anterior, substituindo somente os valores abaixo e o caminho de auditoria por /var/lib/devlite-v7/pack-xx7nyohf/audit.json. O staging anterior, o bootstrap, a unidade, a ISO e os seeds devem ser preservados.

```bash
review="$PWD/work/v7-admin-review-ZtRqyQd2"
archive="$review/worker.tar"
old=c28b1755957f831ff0a19b4162c840930f1a67950a784b72331181b3499eab1a
new=c8ee69fae299a849036d6ff2d9aeda3baa7b1a9b5fc798d260d3c05047cbb940
```

## Retomada após o reset do Live no pack kb_q70jg

Use o bloco de retomada do pack 4dtny274, substituindo os quatro valores abaixo e o caminho da auditoria por /var/lib/devlite-v7/pack-kb_q70jg/audit.json. Preserve o pack, os snapshots, o bootstrap, a unidade, os seeds e a ISO administrativa. Após conferência da auditoria, troca de recibo, pré-voo aprovado e autorização, inicie a mesma unidade.

```bash
review="$PWD/work/v7-admin-review-7POklM5O"
archive="$review/worker.tar"
old=c8ee69fae299a849036d6ff2d9aeda3baa7b1a9b5fc798d260d3c05047cbb940
new=e59e3e119207bed8d2a09bec64e9a3dddf88703f400a94bf19e9b7fa973a981a
```
